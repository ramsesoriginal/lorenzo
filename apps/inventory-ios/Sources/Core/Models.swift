import Foundation

public enum JSONValue: Codable, Equatable, Sendable {
    case string(String), number(Double), bool(Bool), array([JSONValue]), object([String: JSONValue]), null
    public init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let v = try? c.decode(Bool.self) { self = .bool(v) }
        else if let v = try? c.decode(Double.self) { self = .number(v) }
        else if let v = try? c.decode(String.self) { self = .string(v) }
        else if let v = try? c.decode([JSONValue].self) { self = .array(v) }
        else { self = .object(try c.decode([String: JSONValue].self)) }
    }
    public func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .string(let v): try c.encode(v)
        case .number(let v): try c.encode(v)
        case .bool(let v): try c.encode(v)
        case .array(let v): try c.encode(v)
        case .object(let v): try c.encode(v)
        case .null: try c.encodeNil()
        }
    }
    public var display: String {
        switch self {
        case .string(let v): return v
        case .number(let v): return v.formatted()
        case .bool(let v): return v ? "Yes" : "No"
        case .null: return "Not set"
        default: return String(data: (try? JSONEncoder().encode(self)) ?? Data(), encoding: .utf8) ?? ""
        }
    }
}
public enum Wire {
    public static var decoder: JSONDecoder {
        let d = JSONDecoder(); d.keyDecodingStrategy = .convertFromSnakeCase; return d
    }
    public static var encoder: JSONEncoder {
        let e = JSONEncoder(); e.keyEncodingStrategy = .convertToSnakeCase; e.outputFormatting = [.sortedKeys]; return e
    }
}
public struct Character: Codable, Hashable, Identifiable, Sendable {
    public var tenantId: String
    public var entityId: String
    public var name: String
    public var id: String { tenantId + "/" + entityId }
    public init(tenantId: String, entityId: String, name: String) {
        self.tenantId = tenantId; self.entityId = entityId; self.name = name
    }
}
public struct Me: Codable, Sendable {
    public struct Seat: Codable, Sendable {
        public struct Being: Codable, Sendable { public var entityId: String; public var name: String }
        public var tenantId: String; public var characters: [Being]
    }
    public var id: String; public var players: [Seat]; public var locales: [String]?
    public var characters: [Character] {
        var seen = Set<String>()
        return players.flatMap { s in s.characters.map { Character(tenantId: s.tenantId, entityId: $0.entityId, name: $0.name) } }
            .filter { seen.insert($0.id).inserted }.sorted { $0.name.localizedStandardCompare($1.name) == .orderedAscending }
    }
}
public struct EntityRef: Codable, Hashable, Sendable { public var id: String; public var name: String }
public struct Stat: Codable, Hashable, Sendable {
    public var name: String; public var value: JSONValue?
}
extension JSONValue: Hashable {}
public struct Description: Codable, Sendable {
    public var content: String; public var locale: String; public var fromEntity: EntityRef?
}
public struct Item: Codable, Identifiable, Sendable {
    public var entityId: String; public var title: String; public var quantity: Int?
    public var ownerEntityId: String?; public var bound: Bool?
    public var descriptions: [Description]?
    public var physicalStats: [Stat]?; public var economicStats: [Stat]?
    public var destroyableStats: [Stat]?; public var damagingStats: [Stat]?; public var tags: [Stat]?
    public var id: String { entityId }
    public var stats: [Stat] {
        var result = physicalStats ?? []
        result.append(contentsOf: economicStats ?? [])
        result.append(contentsOf: destroyableStats ?? [])
        result.append(contentsOf: damagingStats ?? [])
        result.append(contentsOf: tags ?? [])
        return result
    }
    public func preferredDescriptions(_ locales: [String]) -> [Description] {
        var groups: [[Description]] = []
        for d in descriptions ?? [] {
            if let i = groups.firstIndex(where: { $0.first?.fromEntity?.id == d.fromEntity?.id }) { groups[i].append(d) }
            else { groups.append([d]) }
        }
        return groups.compactMap { candidates in
            for locale in locales {
                if let d = candidates.first(where: { $0.locale.lowercased() == locale.lowercased() }) { return d }
                if let d = candidates.first(where: { $0.locale.split(separator: "-").first?.lowercased() == locale.split(separator: "-").first?.lowercased() }) { return d }
            }
            return candidates.first
        }
    }
}
public struct Inventory: Codable, Sendable {
    public struct Group: Codable, Identifiable, Sendable {
        public var container: EntityRef; public var carried: Bool; public var path: [EntityRef]?
        public var itemInstances: [Item]; public var id: String { container.id }
    }
    public var groups: [Group]; public var owners: [EntityRef]?
}
public struct Payload: Codable, Identifiable, Sendable {
    public var id: String; public var kind: String; public var order: Int
    public var content: String?; public var locale: String?; public var updatedAt: String?
    public var fileType: String?; public var url: String?
}
public struct Information: Codable, Identifiable, Sendable {
    public var id: String; public var title: String; public var type: String
    public var isPublic: Bool; public var updatedAt: String; public var createdByName: String?
    public var payloads: [Payload]
    public var ordered: [Payload] { payloads.sorted { $0.order < $1.order } }
}
public struct Audience: Codable, Equatable, Sendable {
    public var isPublic: Bool; public var entityIds: [String]; public var playerIds: [String]
    public init(isPublic: Bool = false, entityIds: [String] = [], playerIds: [String] = []) {
        self.isPublic = isPublic; self.entityIds = Array(Set(entityIds)).sorted(); self.playerIds = Array(Set(playerIds)).sorted()
    }
    public func matches(_ other: Audience) -> Bool {
        isPublic == other.isPublic && Set(entityIds) == Set(other.entityIds) && Set(playerIds) == Set(other.playerIds)
    }
}
public struct Recipient: Codable, Identifiable, Sendable {
    public var entityId: String; public var name: String; public var id: String { entityId }
    public init(entityId: String, name: String) { self.entityId = entityId; self.name = name }
}
public struct Page<T: Codable & Sendable>: Codable, Sendable { public var items: [T]; public var total: Int }
public struct DeviceCode: Codable, Sendable {
    public var deviceCode: String; public var userCode: String; public var verificationUriComplete: String
    public var interval: Int; public var expiresIn: Int
}
public struct TokenResponse: Codable, Sendable { public var accessToken: String }
public struct DraftPart: Codable, Equatable, Identifiable, Sendable {
    public var id: String = UUID().uuidString.lowercased()
    public var kind: String = "text"; public var text: String = ""
    public var locale: String = "en"; public var image: Data?
    public init(text: String = "", locale: String = "en") { self.text = text; self.locale = locale }
    public init(image: Data) { self.kind = "image"; self.image = image }
}
public struct Draft: Codable, Equatable, Identifiable, Sendable {
    public var id: String = UUID().uuidString.lowercased()
    public var character: Character; public var itemId: String; public var title: String = "Note"
    public var parts: [DraftPart]; public var audience: Audience
    public var sessionId: UUID?
    public var firstPayloadId: String?; public var orderBase: [String]?
    public var queued = false; public var problem: String?; public var attempts = 0
    public var retryAt: Date?; public var created = Date()
    public init(character: Character, itemId: String, locale: String = "en") {
        self.character = character; self.itemId = itemId
        self.parts = [DraftPart(locale: locale)]; self.audience = Audience(entityIds: [character.entityId])
    }
    public var valid: Bool { !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !parts.isEmpty && parts.contains { $0.kind == "image" ? $0.image != nil : !$0.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty } }
}
public struct Snapshot<T: Codable & Sendable>: Codable, Sendable {
    public var value: T; public var downloaded: Date
    public init(_ value: T) { self.value = value; self.downloaded = Date() }
}
