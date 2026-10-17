import XCTest

final class InventoryFlows: XCTestCase {
    func testSignInInventoryPrivateNoteAndOfflineRelaunch() throws {
        let app=XCUIApplication()
        app.launchEnvironment["LORENZO_TEST_API"]="http://127.0.0.1:8874"
        app.launchEnvironment["LORENZO_TEST_RESET"]="1"
        app.launch()
        let token=app.secureTextFields["token"]
        XCTAssertTrue(token.waitForExistence(timeout:15))
        token.tap();token.typeText("local-ui-token")
        app.buttons["Connect"].tap()
        XCTAssertTrue(app.buttons["Brisk"].waitForExistence(timeout:15))
        app.buttons["Brisk"].tap()
        let item=app.buttons.containing(.staticText,identifier:"Ornate Spellbook").firstMatch
        XCTAssertTrue(item.waitForExistence(timeout:15));item.tap()
        XCTAssertTrue(app.staticTexts["Pages bound between two covers."].waitForExistence(timeout:15))
        let screenshot=XCTAttachment(screenshot:app.screenshot());screenshot.name="Inventory detail";screenshot.lifetime = .keepAlways;add(screenshot)
        app.swipeUp()
        let addNote=app.buttons["add-note"]
        XCTAssertTrue(addNote.waitForExistence(timeout:10));addNote.tap()
        let text=app.textViews["Text"]
        XCTAssertTrue(text.waitForExistence(timeout:10));text.tap();text.typeText("Smoke stains on the map.")
        app.buttons["Save note"].tap()
        XCTAssertTrue(app.staticTexts["Smoke stains on the map."].waitForExistence(timeout:20))
        XCTAssertTrue(app.staticTexts["Private"].exists)
        app.terminate()
        app.launchEnvironment["LORENZO_TEST_RESET"]="0"
        app.launch()
        XCTAssertTrue(app.buttons["Brisk"].waitForExistence(timeout:15))
    }
}
