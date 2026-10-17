import SwiftUI
import PhotosUI
import UIKit
import ImageIO

enum Lorenzo {
    static let ink = Color(red: 0.11, green: 0.18, blue: 0.20)
    static let teal = Color(red: 0.11, green: 0.39, blue: 0.47)
    static let gold = Color(red: 0.72, green: 0.54, blue: 0.23)
}
struct MasterMark: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x:256,y:20))
        let curves: [[CGFloat]] = [[268,126,282,193,309,217],[333,239,394,250,492,256],[394,262,333,273,309,295],[282,319,268,386,256,492],[244,386,230,319,203,295],[179,273,118,262,20,256],[118,250,179,239,203,217],[230,193,244,126,256,20]]
        for c in curves { p.addCurve(to: CGPoint(x:c[4],y:c[5]),control1:CGPoint(x:c[0],y:c[1]),control2:CGPoint(x:c[2],y:c[3])) }
        p.closeSubpath(); p.move(to:CGPoint(x:256,y:218))
        let inner: [[CGFloat]] = [[261,232,280,251,294,256],[280,261,261,280,256,294],[251,280,232,261,218,256],[232,251,251,232,256,218]]
        for c in inner {
            p.addCurve(to: CGPoint(x:c[4],y:c[5]),control1:CGPoint(x:c[0],y:c[1]),control2:CGPoint(x:c[2],y:c[3]))
        }
        p.closeSubpath()
        return p.applying(CGAffineTransform(scaleX:rect.width/512,y:rect.height/512))
    }
}
struct RootView: View {
    @EnvironmentObject var store: InventoryStore
    @State private var token = ""
    @State private var confirmSignOut = false
    var body: some View {
        NavigationStack {
            Group {
                if store.signedIn { roster }
                else { signIn }
            }
            .navigationTitle("Lorenzo Inventory")
            .toolbar {
                if store.signedIn {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("Sign out", systemImage:"rectangle.portrait.and.arrow.right") { confirmSignOut = true }
                    }
                }
            }
            .safeAreaInset(edge: .bottom) {
                if !store.status.isEmpty {
                    Text(store.status).font(.footnote).padding().frame(maxWidth:.infinity).background(.regularMaterial)
                        .accessibilityIdentifier("status")
                }
            }
        }
        .tint(Lorenzo.teal)
        .confirmationDialog("Sign out and clear downloaded information and drafts?", isPresented:$confirmSignOut, titleVisibility:.visible) {
            Button("Sign out", role:.destructive) { Task { await store.signOut() } }
        }
    }
    var signIn: some View {
        Form {
            Section {
                HStack { MasterMark().fill(Lorenzo.gold,style:FillStyle(eoFill:true)).frame(width:44,height:44); Text("Keep your inventory close.").font(.custom("Newsreader-Regular",size:26,relativeTo:.title2)) }
                Text("Connect to read your characters’ inventories and keep notes at the table.")
            }
            Section {
                if let code = store.deviceCode {
                    Text(code.userCode).font(.title.monospaced()).textSelection(.enabled)
                    if let url = URL(string: code.verificationUriComplete) { Link("Open account hub",destination:url) }
                    Text("Approve this code in account hub, then return here.").font(.footnote)
                    Button("Cancel connection") { store.cancelLogin() }
                } else { Button("Connect with account hub") { store.beginLogin() } }
            }
            Section("Or use a personal access token") {
                SecureField("Personal access token",text:$token).textInputAutocapitalization(.never).autocorrectionDisabled()
                    .accessibilityIdentifier("token")
                Button("Connect") { let value=token;token="";Task { await store.connect(value) } }
                    .disabled(store.busy || token.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty)
                Text("A connection acts with your account’s permissions. Revoke it in account hub when you no longer need it.").font(.footnote)
            }
        }
    }
    var roster: some View {
        List {
            if store.characters.isEmpty { ContentUnavailableView("No characters yet",systemImage:"person.text.rectangle",description:Text("Your campaign’s characters will appear here once you play them.")) }
            ForEach(store.characters) { character in
                NavigationLink(value:character) {
                    VStack(alignment:.leading) { Text(character.name).font(.headline); Text("Inventory").font(.caption).foregroundStyle(.secondary) }
                }
            }
            if !store.drafts.isEmpty {
                Section("Saved notes") {
                    ForEach(store.drafts) { draft in
                        VStack(alignment:.leading) {
                            Text(draft.title)
                            Text(draft.queued ? (draft.problem ?? "Pending upload") : "Draft").font(.caption).foregroundStyle(.secondary)
                            if draft.queued { Button("Retry") { Task { await store.retry(draft.id) } } }
                        }
                    }
                }
            }
        }
        .navigationDestination(for:Character.self) { InventoryView(character:$0) }
        .refreshable { await store.refreshRoster() }
    }
}
struct InventoryView: View {
    @EnvironmentObject var store: InventoryStore
    let character: Character
    @State private var search = ""
    var body: some View {
        List {
            if let snapshot = store.inventories[character.id] {
                Text("Downloaded \(snapshot.downloaded.formatted(date:.abbreviated,time:.shortened))").font(.caption).foregroundStyle(.secondary)
                ForEach(snapshot.value.groups) { group in
                    Section {
                        ForEach(group.itemInstances.filter { search.isEmpty || $0.title.localizedCaseInsensitiveContains(search) || ($0.tags ?? []).contains(where: { $0.name.localizedCaseInsensitiveContains(search) }) }) { item in
                            NavigationLink {
                                ItemView(character:character,itemId:item.id)
                            } label: {
                                HStack { Text(item.title); Spacer(); if let q=item.quantity { Text("×\(q)").foregroundStyle(.secondary) } }
                            }
                        }
                    } header: {
                        VStack(alignment:.leading) { Text(group.container.name); if !group.carried { Text("Held elsewhere").font(.caption) } }
                    }
                }
            } else { Text("No downloaded inventory. Pull to refresh when connected.").foregroundStyle(.secondary) }
        }
        .navigationTitle(character.name)
        .searchable(text:$search,prompt:"Search inventory or tags")
        .task { await store.loadInventory(character) }
        .refreshable { await store.loadInventory(character) }
    }
}
struct ItemView: View {
    @EnvironmentObject var store: InventoryStore
    let character: Character
    let itemId: String
    @State private var composer: Draft?
    var item: Item? { store.inventories[character.id]?.value.groups.flatMap(\.itemInstances).first { $0.id == itemId } }
    var body: some View {
        Group {
            if let item {
                List {
                    if item.bound == true { Label("Bound",systemImage:"link") }
                    if let owner=item.ownerEntityId, let name=store.inventories[character.id]?.value.owners?.first(where: { $0.id == owner })?.name { LabeledContent("Owner",value:name) }
                    Section("Description") {
                        ForEach(Array(item.preferredDescriptions(store.locales).enumerated()),id:\.offset) { _,description in
                            VStack(alignment:.leading) {
                                if let source=description.fromEntity { Text("From \(source.name)").font(.caption).foregroundStyle(.secondary) }
                                MarkdownText(content:description.content)
                            }
                        }
                    }
                    if !item.stats.isEmpty {
                        Section("Stats and tags") { ForEach(Array(item.stats.enumerated()),id:\.offset) { _,stat in LabeledContent(stat.name,value:stat.value?.display ?? "Not set") } }
                    }
                    Section("Notes") {
                        ForEach(store.noteSnapshot(character,itemId)?.value ?? []) { note in
                            VStack(alignment:.leading,spacing:10) {
                                Text(note.title).font(.headline)
                                Text(note.isPublic ? "Everyone can read this" : "Private").font(.caption).foregroundStyle(.secondary)
                                if let author=note.createdByName { Text("By \(author)").font(.caption).foregroundStyle(.secondary) }
                                ForEach(note.ordered) { payload in
                                    if payload.kind == "description" { MarkdownText(content:payload.content ?? "") }
                                    else if payload.kind == "picture" { ProtectedPicture(data:store.picture(character,payload.id)) }
                                    else { Text("Attachment: \(payload.kind)").font(.caption) }
                                }
                            }.padding(.vertical,4)
                        }
                        if store.noteSnapshot(character,itemId)?.value.isEmpty == true { Text("No notes yet.").foregroundStyle(.secondary) }
                        ForEach(store.drafts.filter { $0.character.id == character.id && $0.itemId == itemId }) { draft in
                            VStack(alignment:.leading) {
                                Text(draft.title).font(.headline)
                                Text(draft.queued ? (draft.problem ?? "Pending upload") : "Draft").font(.caption)
                                if draft.queued { Button("Retry upload") { Task { await store.retry(draft.id) } } }
                                else { Button("Continue note") { composer=draft } }
                            }
                        }
                        Button("Add a note",systemImage:"square.and.pencil") {
                            let draft=Draft(character:character,itemId:itemId,locale:store.locales.first ?? "en")
                            Task { do { try await store.saveDraft(draft);composer=draft } catch { store.status=error.localizedDescription } }
                        }.accessibilityIdentifier("add-note")
                    }
                }.navigationTitle(item.title)
            } else { ContentUnavailableView("Information unavailable",systemImage:"lock",description:Text("Refresh the inventory to check your access.")) }
        }
        .task { await store.loadNotes(character,itemId:itemId) }
        .refreshable { await store.loadNotes(character,itemId:itemId) }
        .sheet(item:$composer) { draft in NoteComposer(initial:draft) }
    }
}
struct MarkdownText: View {
    let content: String
    var body: some View {
        Text((try? AttributedString(markdown:content,options:.init(interpretedSyntax:.inlineOnlyPreservingWhitespace))) ?? AttributedString(content))
            .textSelection(.enabled)
            .environment(\.openURL,OpenURLAction { url in
                ["https","http","mailto"].contains(url.scheme ?? "") ? .systemAction : .discarded
            })
    }
}
struct ProtectedPicture: View {
    let data: Data?
    @State private var zoom = false
    var body: some View {
        if let data, let image=UIImage(data:data) {
            Button { zoom=true } label: { Image(uiImage:image).resizable().scaledToFit().frame(maxHeight:300) }
                .accessibilityLabel("Open picture")
                .sheet(isPresented:$zoom) { NavigationStack { ZoomPicture(image:image).toolbar { Button("Done") { zoom=false } } } }
        } else { Label("Picture not downloaded",systemImage:"photo").foregroundStyle(.secondary) }
    }
}
struct ZoomPicture: UIViewRepresentable {
    let image: UIImage
    func makeUIView(context:Context) -> UIScrollView {
        let scroll=UIScrollView();scroll.minimumZoomScale=1;scroll.maximumZoomScale=6;scroll.delegate=context.coordinator
        let view=UIImageView(image:image);view.contentMode = .scaleAspectFit;view.tag=1
        scroll.addSubview(view);return scroll
    }
    func updateUIView(_ scroll:UIScrollView,context:Context) { scroll.viewWithTag(1)?.frame=scroll.bounds }
    func makeCoordinator() -> Coordinator { Coordinator() }
    final class Coordinator: NSObject,UIScrollViewDelegate { func viewForZooming(in scrollView:UIScrollView)->UIView? { scrollView.viewWithTag(1) } }
}
struct NoteComposer: View {
    @EnvironmentObject var store: InventoryStore
    @Environment(\.dismiss) private var dismiss
    @State var draft: Draft
    @State private var selection: PhotosPickerItem?
    @State private var camera = false
    @State private var readers: [Recipient] = []
    @State private var saving = false
    @State private var loadingImage = false
    @State private var persistence: Task<Void,Never>?
    @State private var saveError = ""
    init(initial:Draft) { _draft=State(initialValue:initial) }
    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Title",text:$draft.title)
                    ForEach($draft.parts) { $part in
                        VStack(alignment:.leading) {
                            if part.kind == "text" {
                                TextEditor(text:$part.text).frame(minHeight:120).accessibilityLabel("Text")
                                TextField("Language",text:$part.locale).textInputAutocapitalization(.never).font(.caption)
                            } else { ProtectedPicture(data:part.image) }
                            HStack {
                                Button("Move up",systemImage:"arrow.up") { move(part.id,-1) }.labelStyle(.iconOnly)
                                Button("Move down",systemImage:"arrow.down") { move(part.id,1) }.labelStyle(.iconOnly)
                                Spacer()
                                Button("Remove",role:.destructive) { draft.parts.removeAll { $0.id == part.id } }
                            }.buttonStyle(.borderless)
                        }
                    }
                    Button("Add text",systemImage:"text.badge.plus") { draft.parts.append(DraftPart(locale:store.locales.first ?? "en")) }
                    PhotosPicker(selection:$selection,matching:.images,preferredItemEncoding:.current) { Label("Choose a picture",systemImage:"photo") }
                    if UIImagePickerController.isSourceTypeAvailable(.camera) {
                        Button("Take a photo",systemImage:"camera") { camera=true }
                    }
                    if loadingImage { ProgressView("Keeping picture with your draft…") }
                }
                Section {
                    DisclosureGroup("Who can read this") {
                        Toggle("Everyone can read this",isOn:$draft.audience.isPublic)
                        Text("Library administrators and the campaign’s GMs retain their existing access. Selected characters’ players and group members can read this note.").font(.footnote)
                        ForEach(readers) { reader in
                            Toggle(reader.name,isOn:Binding(get:{ draft.audience.entityIds.contains(reader.entityId) },set:{ selected in
                                draft.audience.entityIds.removeAll { $0 == reader.entityId };if selected { draft.audience.entityIds.append(reader.entityId) }
                            }))
                        }
                        let missing=Set(draft.audience.entityIds).subtracting(readers.map(\.entityId))
                        ForEach(Array(missing).sorted(),id:\.self) { id in
                            Toggle("Selected reader \(id)",isOn:Binding(get:{true},set:{ _ in draft.audience.entityIds.removeAll { $0 == id } }))
                        }
                        if readers.isEmpty { Text("Connect to load more characters and groups. Saved selections are kept.").font(.footnote) }
                    }
                }
                if !saveError.isEmpty { Text(saveError).foregroundStyle(.red) }
            }
            .disabled(saving || loadingImage)
            .navigationTitle("Note")
            .interactiveDismissDisabled(saving || loadingImage || !saveError.isEmpty)
            .toolbar {
                ToolbarItem(placement:.cancellationAction) {
                    Button("Keep draft") { Task { await keep() } }.disabled(saving || loadingImage)
                }
                ToolbarItem(placement:.confirmationAction) {
                    Button("Save note") {
                        saving=true
                        Task {
                            await persistence?.value
                            do { try await store.submit(draft);dismiss() } catch { saveError=error.localizedDescription }
                            saving=false
                        }
                    }.disabled(!draft.valid || saving || loadingImage)
                }
            }
            .onChange(of:draft) { _,_ in persist() }
            .onChange(of:selection) { _,value in
                guard let value else { return }
                loadingImage=true
                Task {
                    do {
                        guard let data=try await value.loadTransferable(type:Data.self) else { throw URLError(.cannotDecodeContentData) }
                        let bytes=try await Task.detached(priority:.userInitiated) { try PhotoNormalizer.jpeg(data) }.value
                        await appendPicture(bytes)
                    } catch { saveError="This picture could not be kept: \(error.localizedDescription)" }
                    loadingImage=false;selection=nil
                }
            }
            .sheet(isPresented:$camera) { CameraPicker { image in
                camera=false
                guard let image else { return }
                loadingImage=true
                Task {
                    do {
                        guard let data=image.jpegData(compressionQuality:0.95) else { throw URLError(.cannotDecodeContentData) }
                        let bytes=try await Task.detached(priority:.userInitiated) { try PhotoNormalizer.jpeg(data) }.value
                        await appendPicture(bytes)
                    } catch { saveError=error.localizedDescription }
                    loadingImage=false
                }
            } }
            .task { readers=await store.recipients(draft.character) }
        }
    }
    func move(_ id:String,_ offset:Int) {
        guard let i=draft.parts.firstIndex(where:{$0.id == id}),draft.parts.indices.contains(i+offset) else { return }
        draft.parts.swapAt(i,i+offset)
    }
    func persist() {
        let value=draft;let previous=persistence
        persistence=Task {
            await previous?.value
            do { try await store.saveDraft(value);saveError="" } catch { saveError="Your latest edit could not be saved. Keep this page open and retry." }
        }
    }
    func appendPicture(_ bytes:Data) async {
        await persistence?.value
        var next=draft;next.parts.append(DraftPart(image:bytes))
        do { try await store.saveDraft(next);draft=next;saveError="" } catch { saveError="This picture could not be kept. Please try again." }
    }
    func keep() async {
        saving=true;await persistence?.value
        do { try await store.saveDraft(draft);dismiss() } catch { saveError=error.localizedDescription }
        saving=false
    }
}
enum PhotoNormalizer {
    static func jpeg(_ data:Data) throws -> Data {
        guard data.count <= 30*1024*1024,
              let source=CGImageSourceCreateWithData(data as CFData,nil),
              let properties=CGImageSourceCopyPropertiesAtIndex(source,0,nil) as? [CFString:Any],
              let width=properties[kCGImagePropertyPixelWidth] as? Int,
              let height=properties[kCGImagePropertyPixelHeight] as? Int,
              width > 0,height > 0,width <= 20000,height <= 20000,width*height <= 80_000_000,
              let cg=CGImageSourceCreateThumbnailAtIndex(source,0,[kCGImageSourceCreateThumbnailFromImageAlways:true,kCGImageSourceCreateThumbnailWithTransform:true,kCGImageSourceThumbnailMaxPixelSize:4096] as CFDictionary),
              let image=UIImage(cgImage:cg).jpegData(compressionQuality:0.9),image.count <= 10*1024*1024 else { throw URLError(.cannotDecodeContentData) }
        return image
    }
}
struct CameraPicker: UIViewControllerRepresentable {
    var complete:(UIImage?)->Void
    func makeUIViewController(context:Context)->UIImagePickerController {
        let picker=UIImagePickerController();picker.sourceType = .camera;picker.delegate=context.coordinator;return picker
    }
    func updateUIViewController(_ uiViewController:UIImagePickerController,context:Context) {}
    func makeCoordinator()->Coordinator { Coordinator(complete) }
    final class Coordinator:NSObject,UIImagePickerControllerDelegate,UINavigationControllerDelegate {
        let complete:(UIImage?)->Void
        init(_ complete:@escaping(UIImage?)->Void) { self.complete=complete }
        func imagePickerControllerDidCancel(_ picker:UIImagePickerController) { complete(nil) }
        func imagePickerController(_ picker:UIImagePickerController,didFinishPickingMediaWithInfo info:[UIImagePickerController.InfoKey:Any]) { complete(info[.originalImage] as? UIImage) }
    }
}
