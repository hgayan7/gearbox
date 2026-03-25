import SwiftUI
import AppKit

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        DatabaseManager.shared.startDaemon()
    }
    
    func applicationWillTerminate(_ notification: Notification) {
        DatabaseManager.shared.stopDaemon()
    }
}

@main
struct GearboxUIApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var dbManager = DatabaseManager.shared
    @Environment(\.openWindow) var openWindow
    
    var body: some Scene {
        WindowGroup(id: "dashboard") {
            DesktopContentView(dbManager: dbManager)
        }
        
        MenuBarExtra("Gearbox", systemImage: "gearshape.fill") {
            MenuBarContentView(dbManager: dbManager)
        }
        .menuBarExtraStyle(.window)
    }
}
