import SwiftUI
import BackgroundTasks

@main @MainActor struct LorenzoInventoryApp: App {
    @StateObject private var store: InventoryStore
    @Environment(\.scenePhase) private var phase
    init() {
        let value=InventoryStore()
        _store=StateObject(wrappedValue:value)
        BGTaskScheduler.shared.register(forTaskWithIdentifier:"io.lorenzo.inventory.refresh",using:nil) { task in
            let work=Task { @MainActor in
                await value.synchronizeNow()
                task.setTaskCompleted(success:true)
            }
            task.expirationHandler = { work.cancel() }
        }
    }
    var body: some Scene {
        WindowGroup {
            RootView().environmentObject(store)
                .font(.custom("Geist-Regular",size:17,relativeTo:.body))
                .task { await store.restore() }
                .onChange(of:phase) { _,phase in
                    if phase == .active { Task { await store.refreshRoster() };store.startSync() }
                    if phase == .background {
                        let request=BGAppRefreshTaskRequest(identifier:"io.lorenzo.inventory.refresh")
                        request.earliestBeginDate=Date().addingTimeInterval(900)
                        try? BGTaskScheduler.shared.submit(request)
                    }
                }
        }
    }
}
