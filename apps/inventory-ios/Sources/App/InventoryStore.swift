import Foundation
import SwiftUI
import Network

@MainActor final class InventoryStore: ObservableObject {
    @Published var me: Me?
    @Published var characters: [Character] = []
    @Published var inventories: [String: Snapshot<Inventory>] = [:]
    @Published var notes: [String: Snapshot<[Information]>] = [:]
    @Published var drafts: [Draft] = []
    @Published var status = ""
    @Published var signedIn = false
    @Published var busy = false
    @Published var deviceCode: DeviceCode?
    @Published var pictures: [String: Data] = [:]
    private let base: URL
    private let vault: Vault
    private var api: API?
    private var session = UUID()
    private var cacheEpoch = UUID()
    private var syncTask: Task<Void, Never>?
    private var loginTask: Task<Void, Never>?
    private var retryTask: Task<Void, Never>?
    private let monitor = NWPathMonitor()
    init(vault: Vault = Vault()) {
        self.vault = vault
        #if DEBUG && targetEnvironment(simulator)
        if let raw = ProcessInfo.processInfo.environment["LORENZO_TEST_API"],
           let url = URL(string: raw), url.host == "127.0.0.1", url.scheme == "http" { base = url }
        else { base = API.production }
        #else
        base = API.production
        #endif
        monitor.pathUpdateHandler = { [weak self] path in
            if path.status == .satisfied { Task { @MainActor [weak self] in self?.startSync() } }
        }
        monitor.start(queue: DispatchQueue(label: "io.lorenzo.inventory.connectivity"))
    }
    var locales: [String] { me?.locales ?? Locale.preferredLanguages }
    private func check(_ generation: UUID) throws {
        guard session == generation, signedIn, !Task.isCancelled else { throw CancellationError() }
    }
    func restore() async {
        let generation = session
        do {
            guard let token = try await vault.restore(session: generation) else { return }
            guard session == generation else { return }
            api = API(base: base, token: token); signedIn = true
            cacheEpoch = generation
            let savedMe = try await vault.read(Me.self, name: "roster", session: generation)
            try check(generation); me = savedMe
            characters = me?.characters ?? []
            let savedDrafts = try await vault.read([Draft].self, name: "drafts", session: generation) ?? []
            try check(generation); drafts = savedDrafts
            await refreshRoster()
        } catch { status = "The saved connection could not be opened. Connect again." }
    }
    func connect(_ token: String) async {
        guard !busy else { return }
        let attempt = session
        busy = true; defer { busy = false }
        do {
            let clean = token.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !clean.isEmpty else { return }
            let candidate = API(base: base, token: clean)
            let value = try await candidate.me()
            guard session == attempt, !Task.isCancelled else { throw CancellationError() }
            cancelLogin()
            syncTask?.cancel(); retryTask?.cancel()
            session = UUID(); let generation = session; cacheEpoch = generation
            try await vault.connect(token: clean, session: generation)
            guard session == generation else { return }
            resetContent(); api = candidate; signedIn = true; me = value; characters = value.characters
            try await vault.write(value, name: "roster", session: generation)
            startSync()
        } catch { status = error.localizedDescription }
    }
    func signOut() async {
        session = UUID()
        syncTask?.cancel(); syncTask = nil; retryTask?.cancel(); cancelLogin()
        signedIn = false; api = nil; resetContent()
        do { try await vault.clear() } catch { status = "Local data could not be cleared. Please try signing out again." }
    }
    private func resetContent() {
        me = nil; characters = []; inventories = [:]; notes = [:]; drafts = []; pictures = [:]; status = ""
    }
    func beginLogin() {
        cancelLogin()
        loginTask = Task { [weak self] in
            guard let self else { return }
            do {
                let client = API(base: base)
                let code = try await client.beginDevice()
                try Task.checkCancellation()
                guard let uri = URL(string: code.verificationUriComplete), uri.scheme == "https" else { throw URLError(.badURL) }
                deviceCode = code
                let expires = Date().addingTimeInterval(TimeInterval(code.expiresIn))
                var interval = max(1, code.interval)
                while Date() < expires {
                    try await Task.sleep(nanoseconds: UInt64(interval) * 1_000_000_000)
                    do {
                        let token = try await client.pollDevice(code.deviceCode)
                        try Task.checkCancellation()
                        await connect(token); return
                    } catch let e as APIError {
                        let type = e.kind.replacingOccurrences(of: "_", with: "-")
                        if type.contains("slow-down") { interval += 5 }
                        else if !type.contains("authorization-pending") { throw e }
                    }
                }
                status = "This connection code expired. Request another."
                deviceCode = nil
            } catch is CancellationError {} catch { status = error.localizedDescription; deviceCode = nil }
        }
    }
    func cancelLogin() { loginTask?.cancel(); loginTask = nil; deviceCode = nil }
    func refreshRoster() async {
        guard let api else { return }
        let generation = session
        do {
            let value = try await api.me(); try check(generation)
            let removed = Set(characters.map(\.id)).subtracting(value.characters.map(\.id))
            if !removed.isEmpty { try await purgeCache(session: generation) }
            me = value; characters = value.characters
            try await vault.write(value, name: "roster", session: generation)
            status = ""; startSync()
            for character in characters.prefix(3) { await loadInventory(character) }
        } catch { await handle(error, generation: generation) }
    }
    private func checkCache(_ generation: UUID, _ epoch: UUID) throws {
        try check(generation)
        guard cacheEpoch == epoch else { throw CancellationError() }
    }
    private func cache<T: Encodable>(_ value: T, name: String, generation: UUID, epoch: UUID) async throws {
        try checkCache(generation, epoch)
        try await vault.writeCache(value, name: name, session: generation, epoch: epoch)
        try checkCache(generation, epoch)
    }
    private func purgeCache(session generation: UUID) async throws {
        try check(generation)
        cacheEpoch = UUID()
        inventories = [:]; notes = [:]; pictures = [:]
        try await vault.purgeCache(session: generation, epoch: cacheEpoch)
    }
    private func handle(_ error: Error, generation: UUID) async {
        guard session == generation, !(error is CancellationError) else { return }
        if let e = error as? APIError {
            if e.status == 401 { await signOut(); status = "This connection has expired. Connect again."; return }
            if e.status == 403 || e.status == 404 {
                do { try await purgeCache(session: generation) } catch { status = "Cached information could not be cleared."; return }
            }
        }
        status = error.localizedDescription
    }
    func loadInventory(_ character: Character) async {
        guard let api, characters.contains(where: { $0.id == character.id }) else { return }
        let generation = session; let epoch = cacheEpoch; let name = "inventory/" + character.id
        do {
            if inventories[character.id] == nil {
                let saved = try await vault.read(Snapshot<Inventory>.self, name: name, session: generation)
                try checkCache(generation, epoch); inventories[character.id] = saved
            }
            let value = Snapshot(try await api.inventory(character)); try checkCache(generation, epoch)
            try await cache(value, name: name, generation: generation, epoch: epoch)
            try checkCache(generation, epoch); inventories[character.id] = value
        } catch { await handle(error, generation: generation) }
    }
    func loadNotes(_ character: Character, itemId: String) async {
        guard let api, characters.contains(where: { $0.id == character.id }) else { return }
        let generation = session; let epoch = cacheEpoch; let name = "notes/" + character.id + "/" + itemId
        do {
            if notes[name] == nil {
                let saved = try await vault.read(Snapshot<[Information]>.self, name: name, session: generation)
                try checkCache(generation, epoch); notes[name] = saved
            }
            let value = Snapshot(try await api.notes(character.tenantId, itemId)); try checkCache(generation, epoch)
            try await cache(value, name: name, generation: generation, epoch: epoch)
            try checkCache(generation, epoch); notes[name] = value
            for payload in value.value.flatMap(\.payloads) where payload.kind == "picture" {
                await loadPicture(character, payload: payload.id)
            }
        } catch { await handle(error, generation: generation) }
    }
    func noteSnapshot(_ character: Character, _ item: String) -> Snapshot<[Information]>? {
        notes["notes/" + character.id + "/" + item]
    }
    func recipients(_ character: Character) async -> [Recipient] {
        guard let api else { return [] }
        let generation = session; let epoch = cacheEpoch; let name = "recipients/" + character.tenantId
        do {
            let result = try await api.recipients(character.tenantId); try checkCache(generation, epoch)
            try await cache(result, name: name, generation: generation, epoch: epoch)
            return result
        } catch {
            await handle(error, generation: generation)
            guard signedIn, session == generation else { return [] }
            return (try? await vault.read([Recipient].self, name: name, session: generation)) ?? []
        }
    }
    func loadPicture(_ character: Character, payload: String) async {
        guard let api else { return }
        let generation = session; let epoch = cacheEpoch; let name = "picture/" + character.id + "/" + payload
        do {
            if pictures[name] == nil {
                let saved = try await vault.read(Data.self, name: name, session: generation)
                try checkCache(generation, epoch); pictures[name] = saved
            }
            let data = try await api.picture(character.tenantId, payload); try checkCache(generation, epoch)
            try await cache(data, name: name, generation: generation, epoch: epoch)
            try checkCache(generation, epoch); pictures[name] = data
        } catch { await handle(error, generation: generation) }
    }
    func picture(_ character: Character, _ id: String) -> Data? { pictures["picture/" + character.id + "/" + id] }
    func saveDraft(_ draft: Draft) async throws {
        let generation = session; try check(generation)
        let next = try await vault.updateDraft(draft, session: generation)
        try check(generation); drafts = next
    }
    func discardDraft(_ id: String) async throws {
        let generation = session; try check(generation)
        guard !drafts.contains(where: { $0.id == id && $0.queued }) else { throw SyncConflict() }
        let next = try await vault.updateDraft(nil, removing: id, session: generation)
        try check(generation); drafts = next
    }
    func submit(_ value: Draft) async throws {
        guard value.valid else { return }
        var draft = value
        draft.queued = true; draft.problem = nil; draft.retryAt = nil
        try await saveDraft(draft); startSync()
    }
    func retry(_ id: String) async {
        guard var d = drafts.first(where: { $0.id == id }) else { return }
        d.problem = nil; d.retryAt = nil
        do { try await saveDraft(d); startSync() } catch { status = error.localizedDescription }
    }
    func startSync() {
        guard signedIn, syncTask == nil else { return }
        let generation = session
        syncTask = Task { [weak self] in
            await self?.synchronize(generation)
            guard let self, session == generation else { return }
            syncTask = nil
            let wake = drafts.filter { $0.queued && $0.problem == nil }.compactMap(\.retryAt).min()
            if let wake {
                retryTask?.cancel()
                retryTask = Task { [weak self] in
                    do { try await Task.sleep(nanoseconds: UInt64(max(1, wake.timeIntervalSinceNow)) * 1_000_000_000); self?.startSync() } catch {}
                }
            }
        }
    }
    func synchronizeNow() async {
        startSync()
        await syncTask?.value
    }
    private func synchronize(_ generation: UUID) async {
        guard let api else { return }
        for draft in drafts.filter({ $0.queued && $0.problem == nil && ($0.retryAt ?? .distantPast) <= Date() }) {
            do {
                try check(generation)
                guard characters.contains(where: { $0.id == draft.character.id }) else {
                    throw APIError(status: 403, kind: "", message: "This character is no longer in your roster. The draft is kept.")
                }
                try await NoteSync.send(draft, api: api, checkpoint: { [weak self] next in
                    guard let self else { throw CancellationError() }
                    try await self.check(generation); try await self.saveDraft(next)
                }, checkSession: { [weak self] in
                    guard let self else { throw CancellationError() }; try await self.check(generation)
                })
                try check(generation)
                let next = try await vault.updateDraft(nil, removing: draft.id, session: generation)
                try check(generation); drafts = next
                await loadNotes(draft.character, itemId: draft.itemId)
            } catch {
                guard session == generation, !Task.isCancelled else { return }
                if let apiError = error as? APIError, apiError.status == 401 { await signOut(); return }
                guard var pending = drafts.first(where: { $0.id == draft.id }) else { continue }
                pending.attempts += 1
                if error is URLError || (error as? APIError)?.transient == true {
                    pending.retryAt = Date().addingTimeInterval(min(3600, pow(2, Double(min(pending.attempts, 10)))) * 5)
                } else { pending.problem = error.localizedDescription }
                do { try await saveDraft(pending) } catch { status = "The upload status could not be saved. Your earlier draft is kept." }
            }
        }
    }
}
