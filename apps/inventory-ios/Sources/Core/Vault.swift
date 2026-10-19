import CryptoKit
import Foundation
import Security

public actor Vault {
  private let directory: URL
  private let service: String
  private var key: SymmetricKey?
  private var active: UUID?
  private var cacheEpoch: UUID?
  private var cacheReads: [String: UUID] = [:]
  public init(
    directory: URL? = nil,
    service: String = Bundle.main.bundleIdentifier ?? "io.lorenzo.inventory.ios"
  ) {
    self.directory =
      directory
      ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
      .appendingPathComponent("Lorenzo", isDirectory: true)
    self.service = service
  }
  private func query(_ account: String) -> [String: Any] {
    [
      kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
      kSecAttrAccount as String: account,
    ]
  }
  private func secret(_ account: String) throws -> Data? {
    var q = query(account)
    q[kSecReturnData as String] = true
    q[kSecMatchLimit as String] = kSecMatchLimitOne
    var value: CFTypeRef?
    let status = SecItemCopyMatching(q as CFDictionary, &value)
    if status == errSecItemNotFound { return nil }
    guard status == errSecSuccess else { throw VaultError.keychain(status) }
    return value as? Data
  }
  private func setSecret(_ account: String, _ data: Data) throws {
    var q = query(account)
    let status = SecItemUpdate(q as CFDictionary, [kSecValueData as String: data] as CFDictionary)
    if status == errSecSuccess { return }
    guard status == errSecItemNotFound else { throw VaultError.keychain(status) }
    q[kSecValueData as String] = data
    q[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
    let added = SecItemAdd(q as CFDictionary, nil)
    guard added == errSecSuccess else { throw VaultError.keychain(added) }
  }
  public func restore(session: UUID) throws -> String? {
    guard let data = try secret("token"), let keyData = try secret("key"),
      let token = String(data: data, encoding: .utf8)
    else { return nil }
    key = SymmetricKey(data: keyData)
    active = session
    cacheEpoch = session
    return token
  }
  public func connect(token: String, session: UUID) throws {
    try clear()
    let new = SymmetricKey(size: .bits256)
    try setSecret("key", new.withUnsafeBytes { Data($0) })
    try setSecret("token", Data(token.utf8))
    key = new
    active = session
    cacheEpoch = session
  }
  private func file(_ name: String) -> URL {
    directory.appendingPathComponent(
      SHA256.hash(data: Data(name.utf8)).map { String(format: "%02x", $0) }.joined())
  }
  public func write<T: Encodable>(_ value: T, name: String, session: UUID) throws {
    guard active == session, let key else { throw VaultError.stale }
    let cipher = try AES.GCM.seal(Wire.encoder.encode(value), using: key).combined!
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    var dir = directory
    var exclusions = URLResourceValues()
    exclusions.isExcludedFromBackup = true
    try dir.setResourceValues(exclusions)
    let target = file(name)
    try cipher.write(to: target, options: .atomic)
    #if os(iOS)
      try FileManager.default.setAttributes(
        [.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication],
        ofItemAtPath: target.path)
    #endif
  }
  public func read<T: Decodable>(_ type: T.Type, name: String, session: UUID) throws -> T? {
    guard active == session, let key else { throw VaultError.stale }
    guard FileManager.default.fileExists(atPath: file(name).path) else { return nil }
    let data = try AES.GCM.open(
      AES.GCM.SealedBox(combined: Data(contentsOf: file(name))), using: key)
    return try Wire.decoder.decode(type, from: data)
  }
  public func remove(_ name: String, session: UUID) throws {
    guard active == session else { throw VaultError.stale }
    if FileManager.default.fileExists(atPath: file(name).path) {
      try FileManager.default.removeItem(at: file(name))
    }
  }
  public func beginCacheRead(name: String, session: UUID, epoch: UUID, ticket: UUID) throws {
    guard active == session, cacheEpoch == epoch else { throw VaultError.stale }
    cacheReads[name] = ticket
  }
  public func writeCache<T: Encodable>(
    _ value: T, name: String, session: UUID, epoch: UUID, ticket: UUID? = nil
  ) throws {
    guard cacheEpoch == epoch else { throw VaultError.stale }
    if let ticket, cacheReads[name] != ticket { throw VaultError.stale }
    var names = Set(try read([String].self, name: "cache-index", session: session) ?? [])
    names.insert(name)
    // Register first: a crash can leave an absent entry, never an untracked private file.
    try write(Array(names), name: "cache-index", session: session)
    try write(value, name: name, session: session)
  }
  public func purgeCache(session: UUID, epoch: UUID) throws {
    guard active == session else { throw VaultError.stale }
    cacheEpoch = epoch
    cacheReads = [:]
    for name in try read([String].self, name: "cache-index", session: session) ?? [] {
      try remove(name, session: session)
    }
    try write([String](), name: "cache-index", session: session)
  }
  public func updateDraft(_ draft: Draft?, removing id: String? = nil, session: UUID) throws
    -> [Draft]
  {
    var values = try read([Draft].self, name: "drafts", session: session) ?? []
    if let draft {
      if let i = values.firstIndex(where: { $0.id == draft.id }) {
        values[i] = draft
      } else {
        values.append(draft)
      }
    }
    if let id { values.removeAll { $0.id == id } }
    try write(values, name: "drafts", session: session)
    return values
  }
  public func clear() throws {
    active = nil
    key = nil
    cacheEpoch = nil
    cacheReads = [:]
    for name in ["key", "token"] {
      let status = SecItemDelete(query(name) as CFDictionary)
      guard status == errSecSuccess || status == errSecItemNotFound else {
        throw VaultError.keychain(status)
      }
    }
    if FileManager.default.fileExists(atPath: directory.path) {
      try FileManager.default.removeItem(at: directory)
    }
  }
}
public enum VaultError: Error, LocalizedError {
  case keychain(OSStatus)
  case stale
  public var errorDescription: String? {
    switch self {
    case .keychain: return "This device could not securely save the connection. Please try again."
    case .stale: return "This connection changed. Reopen your note before saving."
    }
  }
}
