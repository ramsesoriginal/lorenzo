import XCTest
@testable import InventoryCore

actor NoteServer: Transport {
    var note: [String: Any]?
    var audience: [String: Any] = ["is_public": false, "entity_ids": [String](), "player_ids": [String]()]
    var picture: Data?
    var failPictureResponse = false
    var corruptAudience = false
    var audienceReads = 0
    var pictureIds: [String] = []
    var ordinaryPictureReads = 0
    func configureLostPicture() { failPictureResponse = true }
    func configureAudienceDrift() { corruptAudience = true }
    func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let path = request.url!.path
        let method = request.httpMethod!
        let json = (try? JSONSerialization.jsonObject(with: request.httpBody ?? Data())) as? [String: Any] ?? [:]
        var status = 200
        var result: Any = [:]
        var raw: Data?
        if path.hasSuffix("/editor") {
            if let note { result = note } else { status = 404 }
        } else if path.contains("/entities/") && path.hasSuffix("/information") {
            note = ["id":json["id"]!,"title":json["title"]!,"type":"note","is_public":false,"updated_at":"v1","payloads":[["id":"bootstrap","kind":"description","order":0,"content":json["content"]!,"locale":json["locale"]!,"updated_at":"v1"]]]
            result = note!
        } else if path.hasSuffix("/audience") {
            if method == "PUT" { audience = json }
            audienceReads += method == "GET" ? 1 : 0
            result = corruptAudience && audienceReads > 1 ? ["is_public":true,"entity_ids":[],"player_ids":[]] : audience
        } else if path.hasSuffix("/payloads/order") {
            var parts = note!["payloads"] as! [[String: Any]]
            let ids = json["payload_ids"] as! [String]
            parts.sort { ids.firstIndex(of:$0["id"] as! String)! < ids.firstIndex(of:$1["id"] as! String)! }
            for i in parts.indices { parts[i]["order"] = i }
            note!["payloads"] = parts
        } else if path.hasSuffix("/texts") {
            var parts = note!["payloads"] as! [[String: Any]]
            if !parts.contains(where: { $0["id"] as? String == json["id"] as? String }) {
                parts.append(["id":json["id"]!,"kind":"description","order":parts.count,"content":json["content"]!,"locale":json["locale"]!,"updated_at":"v1"])
            }
            note!["payloads"] = parts
        } else if path.hasSuffix("/payloads") {
            let text = String(decoding:request.httpBody!,as:UTF8.self)
            let id = text.components(separatedBy:"name=\"payload_id\"\r\n\r\n")[1].components(separatedBy:"\r\n")[0]
            pictureIds.append(id)
            var parts = note!["payloads"] as! [[String: Any]]
            if !parts.contains(where: { $0["id"] as? String == id }) { parts.append(["id":id,"kind":"picture","order":parts.count,"updated_at":"v1"]) }
            note!["payloads"] = parts
            picture = Data([1,2,3])
            if failPictureResponse { failPictureResponse = false; throw URLError(\.networkConnectionLost) }
        } else if path.hasSuffix("/content") {
            ordinaryPictureReads += 1
            status = 403
        } else if method == "DELETE" {
            var parts = note!["payloads"] as! [[String: Any]]
            parts.removeAll { $0["id"] as? String == path.components(separatedBy:"/").last }
            note!["payloads"] = parts
        } else { XCTFail("Unexpected route \(method) \(path)") }
        let data = try raw ?? JSONSerialization.data(withJSONObject:result)
        return (data,HTTPURLResponse(url:request.url!,statusCode:status,httpVersion:nil,headerFields:["ETag":#"W/"v1""#,"Content-Type":raw == nil ? "application/json" : "image/jpeg"])!)
    }
}
actor Checkpoints {
    var value: Draft?
    func save(_ value: Draft) { self.value = value }
}
final class NoteSyncTests: XCTestCase {
    func draft() -> Draft {
        var draft=Draft(character:Character(tenantId:"t",entityId:"c",name:"Brisk"),itemId:"item")
        draft.parts=[DraftPart(text:"Map"),DraftPart(image:Data([1,2,3])),DraftPart(text:"The doorway")]
        draft.queued=true
        return draft
    }
    func testLostUploadResponseReplaysSamePictureAndConfirmsWholeBundle() async throws {
        let server=NoteServer();await server.configureLostPicture()
        let points=Checkpoints();let original=draft()
        do { try await NoteSync.send(original,api:API(transport:server),checkpoint:{ await points.save($0) },checkSession:{});XCTFail() } catch {}
        let saved=await points.value
        XCTAssertNotNil(saved?.firstPayloadId)
        try await NoteSync.send(saved!,api:API(transport:server),checkpoint:{ await points.save($0) },checkSession:{})
        let ids=await server.pictureIds
        XCTAssertEqual(ids,[original.parts[1].id,original.parts[1].id])
        let note=await server.note!
        XCTAssertEqual((note["payloads"] as! [[String:Any]]).count,3)
    }
    func testAudienceReadbackMustMatchBeforeSent() async throws {
        let server=NoteServer();await server.configureAudienceDrift()
        do { try await NoteSync.send(draft(),api:API(transport:server),checkpoint:{_ in},checkSession:{});XCTFail() }
        catch { XCTAssertTrue(error is SyncConflict) }
    }
    func testImageOnlyDraftRemovesOnlyItsEmptyBootstrapText() async throws {
        let server=NoteServer();var d=draft();d.parts=[d.parts[1]]
        try await NoteSync.send(d,api:API(transport:server),checkpoint:{_ in},checkSession:{})
        let note=await server.note!
        XCTAssertEqual((note["payloads"] as! [[String:Any]]).map { $0["kind"] as! String },["picture"])
    }
    func testCancelledSessionMakesNoRequest() async throws {
        let server=NoteServer()
        do { try await NoteSync.send(draft(),api:API(transport:server),checkpoint:{_ in},checkSession:{throw CancellationError()});XCTFail() } catch {}
        let note=await server.note
        XCTAssertNil(note)
    }
    func testExplicitAudienceCanExcludeTheEditorWithoutOrdinaryPictureAccess() async throws {
        let server=NoteServer()
        var d=draft();d.audience=Audience(entityIds:["another-character"])
        try await NoteSync.send(d,api:API(transport:server),checkpoint:{_ in},checkSession:{})
        let reads=await server.ordinaryPictureReads
        XCTAssertEqual(reads,0)
        let audience=await server.audience
        XCTAssertEqual(audience["entity_ids"] as? [String],["another-character"])
    }

}
