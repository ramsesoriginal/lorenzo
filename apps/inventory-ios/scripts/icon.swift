import AppKit
import CoreGraphics
let context=CGContext(data:nil,width:1024,height:1024,bitsPerComponent:8,bytesPerRow:4096,space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGImageAlphaInfo.noneSkipLast.rawValue)!
context.setFillColor(CGColor(red:0.96,green:0.95,blue:0.91,alpha:1))
context.fill(CGRect(x:0,y:0,width:1024,height:1024))
context.translateBy(x:128,y:128);context.scaleBy(x:1.5,y:1.5)
context.move(to:CGPoint(x:256,y:20))
let outer:[[CGFloat]]=[[268,126,282,193,309,217],[333,239,394,250,492,256],[394,262,333,273,309,295],[282,319,268,386,256,492],[244,386,230,319,203,295],[179,273,118,262,20,256],[118,250,179,239,203,217],[230,193,244,126,256,20]]
for c in outer { context.addCurve(to:CGPoint(x:c[4],y:c[5]),control1:CGPoint(x:c[0],y:c[1]),control2:CGPoint(x:c[2],y:c[3])) }
context.closePath();context.move(to:CGPoint(x:256,y:218))
let inner:[[CGFloat]]=[[261,232,280,251,294,256],[280,261,261,280,256,294],[251,280,232,261,218,256],[232,251,251,232,256,218]]
for c in inner { context.addCurve(to:CGPoint(x:c[4],y:c[5]),control1:CGPoint(x:c[0],y:c[1]),control2:CGPoint(x:c[2],y:c[3])) }
context.closePath();context.setFillColor(CGColor(red:0.72,green:0.54,blue:0.23,alpha:1));context.drawPath(using:.eoFill)
let bitmap=NSBitmapImageRep(cgImage:context.makeImage()!)
try bitmap.representation(using:.png,properties:[:])!.write(to:URL(fileURLWithPath:"Resources/Assets.xcassets/AppIcon.appiconset/Icon.png"))
