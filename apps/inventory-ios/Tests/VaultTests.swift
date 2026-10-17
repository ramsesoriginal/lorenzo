import XCTest
@testable import InventoryCore

final class VaultTests: XCTestCase {
    func testEncryptionPersistenceAndSessionFencing() async throws {
        let root=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let service="lorenzo-tests."+UUID().uuidString
        let vault=Vault(directory:root,service:service)
        let one=UUID()
        try await vault.connect(token:"test-token",session:one)
        try await vault.write("secret map",name:"note",session:one)
        let bytes=try Data(contentsOf:FileManager.default.contentsOfDirectory(at:root,includingPropertiesForKeys:nil)[0])
        XCTAssertFalse(String(decoding:bytes,as:UTF8.self).contains("secret map"))
        let reopened=Vault(directory:root,service:service)
        let two=UUID()
        let token=try await reopened.restore(session:two)
        XCTAssertEqual(token,"test-token")
        let text=try await reopened.read(String.self,name:"note",session:two)
        XCTAssertEqual(text,"secret map")
        // Same-token reconnection must still reject work from the old session.
        try await reopened.connect(token:"test-token",session:UUID())
        do { try await reopened.write("old session",name:"note",session:two);XCTFail() } catch {}
        try await reopened.clear()
        XCTAssertFalse(FileManager.default.fileExists(atPath:root.path))
    }
    func testCiphertextTamperingFailsClosed() async throws {
        let root=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let vault=Vault(directory:root,service:"lorenzo-tests."+UUID().uuidString)
        let session=UUID()
        try await vault.connect(token:"token",session:session)
        try await vault.write("private",name:"note",session:session)
        let file=try FileManager.default.contentsOfDirectory(at:root,includingPropertiesForKeys:nil)[0]
        try Data("changed".utf8).write(to:file)
        do { let _:String?=try await vault.read(String.self,name:"note",session:session);XCTFail() } catch {}
        try await vault.clear()
    }
    func testRevocationFencesInflightCacheWrites() async throws {
        let root=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let vault=Vault(directory:root,service:"lorenzo-tests."+UUID().uuidString)
        let session=UUID()
        try await vault.connect(token:"token",session:session)
        try await vault.writeCache("private",name:"image",session:session,epoch:session)
        try await vault.purgeCache(session:session,epoch:UUID())
        do { try await vault.writeCache("stale",name:"image",session:session,epoch:session);XCTFail() } catch {}
        let image=try await vault.read(String.self,name:"image",session:session)
        XCTAssertNil(image)
        try await vault.clear()
    }

}
