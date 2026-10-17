import XCTest
import InventoryCore
@testable import InventoryState

actor LoginWire: Transport {
    var pending: CheckedContinuation<Void,Never>?
    var waitForRelease = false
    var started = false
    func delayLogin() { waitForRelease = true }
    func releaseLogin() { pending?.resume(); pending = nil; waitForRelease = false }
    func send(_ request:URLRequest) async throws -> (Data,HTTPURLResponse) {
        started = true
        if waitForRelease { await withCheckedContinuation { pending = $0 } }
        let data=Data(#"{"id":"user","players":[{"tenant_id":"t","characters":[{"entity_id":"c","name":"Brisk"}]}]}"#.utf8)
        return (data,HTTPURLResponse(url:request.url!,statusCode:200,httpVersion:nil,headerFields:[:])!)
    }
}
actor NoteReadWire: Transport {
    var showNote = true
    func revokeNote() { showNote = false }
    func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let path = request.url!.path
        var json = ""
        var data: Data?
        if path == "/me" {
            json = #"{"id":"user","players":[{"tenant_id":"t","characters":[{"entity_id":"c","name":"Brisk"}]}]}"#
        } else if path.hasSuffix("/content") {
            data = Data([1,2,3])
        } else if showNote {
            json = #"{"items":[{"id":"note","title":"Map","type":"note","is_public":false,"updated_at":"v","payloads":[{"id":"picture","kind":"picture","order":0}]}],"total":1}"#
        } else { json = #"{"items":[],"total":0}"# }
        return (data ?? Data(json.utf8),HTTPURLResponse(url:request.url!,statusCode:200,httpVersion:nil,headerFields:["Content-Type":data == nil ? "application/json" : "image/jpeg"])!)
    }
}
@MainActor final class SessionTests: XCTestCase {
    func store(_ wire: any Transport) -> InventoryStore {
        let vault=Vault(directory:FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString),service:"lorenzo-tests."+UUID().uuidString)
        return InventoryStore(vault:vault,transport:wire)
    }
    func testLateLoginCannotUndoSignOut() async throws {
        let wire=LoginWire();await wire.delayLogin()
        let state=store(wire)
        let login=Task { await state.connect("token") }
        while !(await wire.started) { await Task.yield() }
        await state.signOut();await wire.releaseLogin();await login.value
        XCTAssertFalse(state.signedIn)
        XCTAssertTrue(state.characters.isEmpty)
    }
    func testLateMediaCannotCrossSameTokenReconnection() async throws {
        let state=store(LoginWire())
        await state.connect("token")
        let character=InventoryCore.Character(tenantId:"t",entityId:"c",name:"Brisk")
        var old=state.newDraft(character,itemId:"i")
        old.parts=[DraftPart(image:Data([1,2,3]))]
        try await state.saveDraft(old)
        await state.signOut();await state.connect("token")
        do { try await state.saveDraft(old);XCTFail() } catch {}
        XCTAssertTrue(state.drafts.isEmpty)
        await state.signOut()
    }
    func testDraftSurvivesWithoutNetworkingBeforeQueued() async throws {
        let state=store(LoginWire());await state.connect("token")
        let character=InventoryCore.Character(tenantId:"t",entityId:"c",name:"Brisk")
        var draft=state.newDraft(character,itemId:"i");draft.parts[0].text="The map"
        try await state.saveDraft(draft)
        XCTAssertEqual(state.drafts.first?.parts.first?.text,"The map")
        XCTAssertEqual(state.drafts.first?.queued,false)
        await state.signOut()
    }
    func testHiddenNotesRemoveTheirDownloadedPictures() async throws {
        let wire=NoteReadWire()
        let state=store(wire);await state.connect("token")
        let character=InventoryCore.Character(tenantId:"t",entityId:"c",name:"Brisk")
        await state.loadNotes(character,itemId:"i")
        XCTAssertNotNil(state.picture(character,"picture"))
        await wire.revokeNote()
        await state.loadNotes(character,itemId:"i")
        XCTAssertNil(state.picture(character,"picture"))
        XCTAssertEqual(state.noteSnapshot(character,"i")?.value.count,0)
        await state.signOut()
    }

}
