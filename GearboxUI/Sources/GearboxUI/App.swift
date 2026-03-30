import SwiftUI
import AppKit

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        DatabaseManager.shared.syncSchedules()
        DatabaseManager.shared.fetchData()
    }
}

@main
struct GearboxUIApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var dbManager = DatabaseManager.shared
    @Environment(\.openWindow) var openWindow
    @Environment(\.scenePhase) private var scenePhase
    
    var body: some Scene {
        WindowGroup(id: "dashboard") {
            DesktopContentView(dbManager: dbManager)
        }
        
        MenuBarExtra {
            MenuBarContentView(dbManager: dbManager)
        } label: {
            Image(nsImage: MenuBarIcon.appIcon)
        }
        .menuBarExtraStyle(.window)
        .onChange(of: scenePhase) { phase in
            if phase == .active {
                dbManager.fetchData()
            }
        }
    }
}

private enum MenuBarIcon {
    static let appIcon: NSImage = {
        let fallback = NSImage(systemSymbolName: "gearshape.fill", accessibilityDescription: "Gearbox") ?? NSImage()
        guard
            let url = Bundle.module.url(forResource: "AppIcon", withExtension: "png"),
            let image = NSImage(contentsOf: url)
        else {
            return fallback
        }

        let targetSize = NSSize(width: 18, height: 18)
        let resizedImage = NSImage(size: targetSize)
        resizedImage.lockFocus()
        image.draw(in: NSRect(origin: .zero, size: targetSize))
        resizedImage.unlockFocus()
        resizedImage.isTemplate = false
        return resizedImage
    }()
}
