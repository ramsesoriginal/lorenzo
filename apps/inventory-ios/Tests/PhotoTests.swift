import ImageIO
import UniformTypeIdentifiers
import XCTest

@testable import InventoryCore

final class PhotoTests: XCTestCase {
  func testOrientationIsAppliedAndOriginalBytesAreUntouched() throws {
    let context = CGContext(
      data: nil, width: 4, height: 2, bitsPerComponent: 8, bytesPerRow: 16,
      space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
    context.setFillColor(CGColor(red: 1, green: 0, blue: 0, alpha: 1))
    context.fill(CGRect(x: 0, y: 0, width: 4, height: 2))
    let original = NSMutableData()
    let destination = CGImageDestinationCreateWithData(
      original, UTType.jpeg.identifier as CFString, 1, nil)!
    CGImageDestinationAddImage(
      destination, context.makeImage()!, [kCGImagePropertyOrientation: 6] as CFDictionary)
    XCTAssertTrue(CGImageDestinationFinalize(destination))
    let input = original as Data
    let normalized = try PhotoNormalizer.jpeg(input)
    let source = CGImageSourceCreateWithData(normalized as CFData, nil)!
    let image = CGImageSourceCreateImageAtIndex(source, 0, nil)!
    XCTAssertEqual(image.width, 2)
    XCTAssertEqual(image.height, 4)
    XCTAssertEqual(original as Data, input)
  }
  func testInvalidOrOversizedDataIsRejected() {
    XCTAssertThrowsError(try PhotoNormalizer.jpeg(Data("not an image".utf8)))
    XCTAssertThrowsError(try PhotoNormalizer.jpeg(Data(repeating: 0, count: 31 * 1024 * 1024)))
  }
}
