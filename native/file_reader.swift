import Foundation
import PDFKit
import Vision
import AppKit
import ImageIO
func ocr(_ image: CGImage) -> String {
 let request=VNRecognizeTextRequest();request.recognitionLevel = .accurate;request.recognitionLanguages=["ja-JP","en-US"];request.usesLanguageCorrection=true
 do {try VNImageRequestHandler(cgImage:image,options:[:]).perform([request]);return (request.results ?? []).compactMap{$0.topCandidates(1).first?.string}.joined(separator:"\n")} catch {return ""}
}
let url=URL(fileURLWithPath:CommandLine.arguments[1]);var text="";var recognized=false;var status="読取済み"
if url.pathExtension.lowercased()=="pdf" {
 if let doc=PDFDocument(url:url), !doc.isLocked {
  let count=min(doc.pageCount,40);if doc.pageCount>40 {status="一部読取（先頭40ページ）"}
  for i in 0..<count {if let page=doc.page(at:i) {var value=page.string ?? "";if value.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty {let image=page.thumbnail(of:NSSize(width:1600,height:2200),for:.mediaBox);var rect=NSRect(origin:.zero,size:image.size);if let cg=image.cgImage(forProposedRect:&rect,context:nil,hints:nil){value=ocr(cg)}};if !value.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty{recognized=true}else{status="一部読取（文字を取得できないページあり）"};text += "\nページ \(i+1)\n"+value;if text.count>100000{status="一部読取（文字数上限）";break}}}
 } else {status="暗号化・読取要確認"}
} else {
 if let src=CGImageSourceCreateWithURL(url as CFURL,nil),let image=CGImageSourceCreateImageAtIndex(src,0,nil){text=ocr(image);recognized = !text.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty;status="画像OCR（認識内容の確認が必要）"} else {status="画像形式の読取未対応"}
}
if !recognized && !status.contains("暗号化") {status="文字を取得できませんでした・要確認"}
let value:[String:String]=["text":String(text.prefix(100000)),"status":status]
if let data=try? JSONSerialization.data(withJSONObject:value),let result=String(data:data,encoding:.utf8){print(result)}
