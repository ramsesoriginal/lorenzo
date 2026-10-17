import Foundation

public struct APIError: Error, LocalizedError, Sendable {
    public var status: Int; public var kind: String; public var message: String
    public init(status: Int, kind: String, message: String) { self.status = status; self.kind = kind; self.message = message }
    public var errorDescription: String? { message }
    public var transient: Bool { status == 408 || status == 429 || status >= 500 }
}
public struct Reply: Sendable { public var data: Data; public var etag: String; public var mime: String }
public protocol Transport: Sendable {
    func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse)
}
private final class NoRedirects: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    static let shared = NoRedirects()
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }
}
public final class HTTPTransport: Transport, @unchecked Sendable {
    private let session: URLSession
    public init() {
        let c = URLSessionConfiguration.ephemeral
        c.timeoutIntervalForRequest = 30; c.timeoutIntervalForResource = 45
        c.urlCache = nil; c.httpCookieStorage = nil
        session = URLSession(configuration: c, delegate: NoRedirects.shared, delegateQueue: nil)
    }
    deinit { session.invalidateAndCancel() }
    public func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let (bytes, response) = try await session.bytes(for: request)
        guard let response = response as? HTTPURLResponse else { throw URLError(.badServerResponse) }
        guard response.expectedContentLength <= 10 * 1024 * 1024 else { throw URLError(.dataLengthExceedsMaximum) }
        var data = Data()
        for try await byte in bytes {
            guard data.count < 10 * 1024 * 1024 else { throw URLError(.dataLengthExceedsMaximum) }
            data.append(byte)
        }
        return (data, response)
    }

}
public struct API: Sendable {
    public static let production = URL(string: "https://lorenzo-api-100817212329.europe-west1.run.app/")!
    public let base: URL
    private let token: String?
    private let transport: any Transport
    public init(base: URL = API.production, token: String? = nil, transport: any Transport = HTTPTransport()) {
        self.base = base; self.token = token; self.transport = transport
    }
    public func request(_ path: [String], method: String = "GET", body: Data? = nil, query: [URLQueryItem] = [], etag: String? = nil, mime: String = "application/json") async throws -> Reply {
        guard base.scheme == "https" || (base.scheme == "http" && ["localhost", "127.0.0.1"].contains(base.host ?? "")),
              path.allSatisfy({ !$0.isEmpty && !$0.contains("/") && $0 != "." && $0 != ".." }) else { throw URLError(.badURL) }
        var url = base
        for part in path { url.appendPathComponent(part) }
        var components = URLComponents(url: url, resolvingAgainstBaseURL: false)!
        if !query.isEmpty { components.queryItems = query }
        var req = URLRequest(url: components.url!)
        req.httpMethod = method; req.httpBody = body
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token { req.setValue("Bearer " + token, forHTTPHeaderField: "Authorization") }
        if body != nil { req.setValue(mime, forHTTPHeaderField: "Content-Type") }
        if let etag { req.setValue(etag, forHTTPHeaderField: "If-Match") }
        let (data, response) = try await transport.send(req)
        guard (200..<300).contains(response.statusCode) else {
            let p = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            throw APIError(status: response.statusCode, kind: p?["type"] as? String ?? "", message: p?["detail"] as? String ?? p?["title"] as? String ?? "Request failed (\(response.statusCode)).")
        }
        return Reply(data: data, etag: response.value(forHTTPHeaderField: "ETag") ?? "", mime: response.mimeType ?? "")
    }
    public func get<T: Decodable>(_ path: [String], as type: T.Type = T.self) async throws -> T {
        try Wire.decoder.decode(type, from: await request(path).data)
    }
    public func json<T: Encodable>(_ value: T) throws -> Data { try Wire.encoder.encode(value) }
    public func me() async throws -> Me { try await get(["me"]) }
    public func inventory(_ c: Character) async throws -> Inventory { try await get(["tenants", c.tenantId, "item-instances", "held-by", c.entityId]) }
    public func information(_ tenant: String, _ id: String) -> [String] { ["tenants", tenant, "information", id] }
    public func notes(_ tenant: String, _ item: String) async throws -> [Information] {
        try await pages(["tenants", tenant, "entities", item, "information"], query: [URLQueryItem(name: "type", value: "note")])
    }
    public func pages<T: Codable & Sendable>(_ path: [String], query: [URLQueryItem] = []) async throws -> [T] {
        var all: [T] = []; var page = 1
        while page <= 1000 {
            let reply = try await request(path, query: query + [URLQueryItem(name: "page", value: String(page)), URLQueryItem(name: "size", value: "100")])
            let result = try Wire.decoder.decode(Page<T>.self, from: reply.data)
            all += result.items
            if all.count >= result.total || result.items.isEmpty { return all }
            page += 1
        }
        throw APIError(status: 0, kind: "", message: "The list is too long to download.")
    }
    public func recipients(_ tenant: String) async throws -> [Recipient] {
        let characters: [Recipient] = try await pages(["tenants", tenant, "characters"])
        let groups: [EntityRef] = try await pages(["tenants", tenant, "groups"])
        return (characters + groups.map { Recipient(entityId: $0.id, name: $0.name + " (group)") }).sorted { $0.name < $1.name }
    }
    public func beginDevice() async throws -> DeviceCode {
        let reply = try await request(["device-codes"], method: "POST", body: json(["client_name": "Lorenzo Inventory on iOS"]))
        return try Wire.decoder.decode(DeviceCode.self, from: reply.data)
    }
    public func pollDevice(_ code: String) async throws -> String {
        let reply = try await request(["device-codes", "token"], method: "POST", body: json(["device_code": code]))
        return try Wire.decoder.decode(TokenResponse.self, from: reply.data).accessToken
    }
    public func picture(_ tenant: String, _ id: String) async throws -> Data {
        let reply = try await request(["tenants", tenant, "payloads", id, "content"])
        guard ["image/jpeg", "image/png", "image/webp", "image/gif"].contains(reply.mime) else { throw URLError(.cannotDecodeContentData) }
        return reply.data
    }
    public func upload(_ tenant: String, _ info: String, part: DraftPart, etag: String) async throws {
        guard let image = part.image, image.count <= 10 * 1024 * 1024 else { throw URLError(.dataLengthExceedsMaximum) }
        let boundary = "Lorenzo-" + UUID().uuidString
        var data = Data("--\(boundary)\r\nContent-Disposition: form-data; name=\"payload_id\"\r\n\r\n\(part.id)\r\n--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"picture.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".utf8)
        data.append(image); data.append(Data("\r\n--\(boundary)--\r\n".utf8))
        _ = try await request(information(tenant, info) + ["payloads"], method: "POST", body: data, etag: etag, mime: "multipart/form-data; boundary=" + boundary)
    }
}
