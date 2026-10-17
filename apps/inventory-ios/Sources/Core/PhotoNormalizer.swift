import Foundation
import ImageIO
import UniformTypeIdentifiers

public enum PhotoNormalizer {
    public static func thumbnail(_ data: Data) throws -> CGImage {
        guard data.count <= 30 * 1024 * 1024,
            let source = CGImageSourceCreateWithData(data as CFData, nil),
            let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any],
            let width = properties[kCGImagePropertyPixelWidth] as? Int,
            let height = properties[kCGImagePropertyPixelHeight] as? Int,
            width > 0, height > 0, width <= 20_000, height <= 20_000, width * height <= 80_000_000,
            let image = CGImageSourceCreateThumbnailAtIndex(source, 0, [
                kCGImageSourceCreateThumbnailFromImageAlways: true,
                kCGImageSourceCreateThumbnailWithTransform: true,
                kCGImageSourceThumbnailMaxPixelSize: 4096
            ] as CFDictionary)
        else { throw URLError(.cannotDecodeContentData) }
        return image
    }
    public static func jpeg(_ data: Data) throws -> Data {
        let image = try thumbnail(data)
        let bytes = NSMutableData()
        guard let destination = CGImageDestinationCreateWithData(bytes, UTType.jpeg.identifier as CFString, 1, nil)
        else { throw URLError(.cannotDecodeContentData) }
        CGImageDestinationAddImage(destination, image, [kCGImageDestinationLossyCompressionQuality: 0.9] as CFDictionary)
        guard CGImageDestinationFinalize(destination), bytes.length <= 10 * 1024 * 1024
        else { throw URLError(.dataLengthExceedsMaximum) }
        return bytes as Data
    }
}
