import XCTest

@testable import InventoryCore

actor Stub: Transport {
  var responses: [(Int, String, [String: String])]
  var requests: [URLRequest] = []
  init(_ responses: [(Int, String, [String: String])]) { self.responses = responses }
  func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
    requests.append(request)
    let next = responses.removeFirst()
    return (
      Data(next.1.utf8),
      HTTPURLResponse(
        url: request.url!, statusCode: next.0, httpVersion: nil, headerFields: next.2)!
    )
  }
}
final class ContractTests: XCTestCase {
  func testRosterDeduplicatesAcrossSeatsButNotLibraries() throws {
    let me = try Wire.decoder.decode(
      Me.self,
      from: Data(
        #"{"id":"u","players":[{"tenant_id":"a","characters":[{"entity_id":"c","name":"Brisk"}]},{"tenant_id":"a","characters":[{"entity_id":"c","name":"Brisk"}]},{"tenant_id":"b","characters":[{"entity_id":"c","name":"Ashfang"}]}]}"#
          .utf8))
    XCTAssertEqual(me.characters.map(\.id), ["b/c", "a/c"])
  }
  func testInventoryRetainsZeroAndUnknownFields() throws {
    let data = Data(
      #"{"groups":[{"container":{"id":"c","name":"Equipped"},"carried":true,"item_instances":[{"entity_id":"i","title":"Book","quantity":0,"physical_stats":[{"name":"Weight","value":0}],"new_field":true}]}]}"#
        .utf8)
    let inventory = try Wire.decoder.decode(Inventory.self, from: data)
    XCTAssertEqual(inventory.groups[0].itemInstances[0].quantity, 0)
    XCTAssertEqual(inventory.groups[0].itemInstances[0].stats[0].value, .number(0))
  }
  func testPaginationAndAuthorization() async throws {
    let stub = Stub([
      (
        200,
        #"{"items":[{"id":"one","title":"Note","type":"note","is_public":false,"updated_at":"v","payloads":[]}],"total":2}"#,
        [:]
      ),
      (
        200,
        #"{"items":[{"id":"two","title":"Note","type":"note","is_public":false,"updated_at":"v","payloads":[]}],"total":2}"#,
        [:]
      ),
    ])
    let api = API(token: "test-token", transport: stub)
    let notes = try await api.notes("library", "item")
    XCTAssertEqual(notes.map(\.id), ["one", "two"])
    let requests = await stub.requests
    XCTAssertTrue(requests[1].url!.absoluteString.contains("page=2"))
    XCTAssertEqual(requests[0].value(forHTTPHeaderField: "Authorization"), "Bearer test-token")
  }
  func testProblemsAndOriginGuard() async throws {
    let stub = Stub([(403, #"{"title":"Forbidden","detail":"This note is private."}"#, [:])])
    do {
      _ = try await API(transport: stub).request(["me"])
      XCTFail()
    } catch let e as APIError {
      XCTAssertEqual(e.status, 403)
      XCTAssertEqual(e.message, "This note is private.")
    }
    do {
      _ = try await API(base: URL(string: "http://example.com")!, transport: stub).request(["me"])
      XCTFail()
    } catch { XCTAssertEqual((error as? URLError)?.code, .badURL) }
  }
  func testMultipartContractAndETag() async throws {
    let stub = Stub([(201, "{}", [:])])
    var part = DraftPart(image: Data([1, 2, 3]))
    part.id = "stable-id"
    try await API(transport: stub).upload("t", "i", part: part, etag: #""v1""#)
    let request = await stub.requests[0]
    let body = String(decoding: request.httpBody!, as: UTF8.self)
    XCTAssertTrue(body.contains(#"name="file""#))
    XCTAssertTrue(body.contains(#"name="payload_id""#))
    XCTAssertTrue(body.contains("stable-id"))
    XCTAssertEqual(request.value(forHTTPHeaderField: "If-Match"), #""v1""#)
  }
  func testRejectsHeaderControlCharactersBeforeNetworking() async throws {
    let stub = Stub([])
    do {
      _ = try await API(token: "one\ntwo", transport: stub).request(["me"])
      XCTFail()
    } catch {
      XCTAssertEqual((error as? APIError)?.status, 0)
    }
    let requests = await stub.requests
    XCTAssertTrue(requests.isEmpty)
  }
}
