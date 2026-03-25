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
        
        MenuBarExtra {
            MenuBarContentView(dbManager: dbManager)
        } label: {
            Image(nsImage: MenuBarIcon.appIcon)
        }
        .menuBarExtraStyle(.window)
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
