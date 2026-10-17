import Foundation
import CryptoKit

public struct SyncConflict: Error, LocalizedError {
    public init() {}
    public var errorDescription: String? { "This note changed elsewhere. Your draft is kept for review." }
}
public struct NoteSync {
    private struct Create: Encodable { var id: String; var title: String; var type = "note"; var isPublic = false; var content: String; var locale: String }
    private struct Text: Encodable { var id: String; var content: String; var locale: String }
    public static func send(_ original: Draft, api: API, checkpoint: @escaping (Draft) async throws -> Void, checkSession: @escaping () async throws -> Void) async throws {
        var draft = original
        let tenant = draft.character.tenantId
        let path = api.information(tenant, draft.id)
        let first = draft.parts.first { $0.kind == "text" }
        func editor() async throws -> (Information, String) {
            try await checkSession()
            let r = try await api.request(path + ["editor"])
            try await checkSession()
            return (try Wire.decoder.decode(Information.self, from: r.data), r.etag)
        }
        var current: (Information, String)
        do { current = try await editor() }
        catch let error as APIError where error.status == 404 && draft.firstPayloadId == nil {
            _ = try await api.request(["tenants", tenant, "entities", draft.itemId, "information"], method: "POST",
                                      body: api.json(Create(id: draft.id, title: draft.title, content: first?.text ?? "", locale: first?.locale ?? "en")))
            current = try await editor()
        }
        guard current.0.title == draft.title && current.0.type == "note" else { throw SyncConflict() }
        if draft.firstPayloadId == nil {
            guard let initial = current.0.payloads.first(where: { $0.kind == "description" }),
                  initial.content == (first?.text ?? ""), initial.locale == (first?.locale ?? "en") else { throw SyncConflict() }
            draft.firstPayloadId = initial.id
            try await checkpoint(draft)
        }
        func serverId(_ part: DraftPart) -> String { part.id == first?.id ? draft.firstPayloadId! : part.id }
        func validate(_ information: Information, complete: Bool) throws {
            let allowed = Set(draft.parts.map(serverId) + [draft.firstPayloadId!])
            guard information.payloads.allSatisfy({ allowed.contains($0.id) }) else { throw SyncConflict() }
            for part in draft.parts {
                let payload = information.payloads.first { $0.id == serverId(part) }
                if complete && payload == nil { throw SyncConflict() }
                if let payload {
                    guard payload.kind == (part.kind == "text" ? "description" : "picture") else { throw SyncConflict() }
                    if part.kind == "text" && (payload.content != part.text || payload.locale != part.locale) { throw SyncConflict() }
                }
            }
            if first == nil, let initial = information.payloads.first(where: { $0.id == draft.firstPayloadId }) {
                guard initial.kind == "description" && initial.content == "" else { throw SyncConflict() }
            }
        }
        try validate(current.0, complete: false)
        for part in draft.parts {
            try await checkSession()
            if part.kind == "image" {
                var upload = part; upload.id = serverId(part)
                try await api.upload(tenant, draft.id, part: upload, etag: current.1)
            } else if !current.0.payloads.contains(where: { $0.id == serverId(part) }) {
                _ = try await api.request(path + ["texts"], method: "POST", body: api.json(Text(id: serverId(part), content: part.text, locale: part.locale)), etag: current.1)
            }
            current = try await editor()
            try validate(current.0, complete: false)
        }
        if first == nil, let placeholder = current.0.payloads.first(where: { $0.id == draft.firstPayloadId }) {
            _ = try await api.request(["tenants", tenant, "payloads", placeholder.id], method: "DELETE", etag: "W/\"\(placeholder.updatedAt ?? "")\"")
            current = try await editor()
        }
        let wanted = draft.parts.map(serverId)
        if draft.orderBase == nil {
            draft.orderBase = (first == nil ? [] : [draft.firstPayloadId!]) + draft.parts.filter { $0.id != first?.id }.map(serverId)
            try await checkpoint(draft)
        }
        let actual = current.0.ordered.map(\.id)
        if actual != wanted {
            guard actual == draft.orderBase else { throw SyncConflict() }
            _ = try await api.request(path + ["payloads", "order"], method: "PUT", body: api.json(["payload_ids": wanted]), etag: current.1)
        }
        let readers = try await api.request(path + ["audience"])
        let audience = try Wire.decoder.decode(Audience.self, from: readers.data)
        if !audience.matches(draft.audience) {
            guard audience.matches(Audience()) else { throw SyncConflict() }
            _ = try await api.request(path + ["audience"], method: "PUT", body: api.json(draft.audience), etag: readers.etag)
        }
        let confirmed = try await editor().0
        try validate(confirmed, complete: true)
        guard confirmed.ordered.map(\.id) == wanted else { throw SyncConflict() }
        let readback: Audience = try await api.get(path + ["audience"])
        guard readback.matches(draft.audience) else { throw SyncConflict() }
        for part in draft.parts where part.kind == "image" {
            let bytes = try await api.picture(tenant, serverId(part))
            guard SHA256.hash(data: bytes) == SHA256.hash(data: part.image ?? Data()) else { throw SyncConflict() }
        }
        try await checkSession()
    }
}
