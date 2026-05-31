import SwiftUI
import AppKit
import UserNotifications

class AppDelegate: NSObject, NSApplicationDelegate, UNUserNotificationCenterDelegate {
    func applicationWillFinishLaunching(_ notification: Notification) {
        let runningApps = NSRunningApplication.runningApplications(withBundleIdentifier: Bundle.main.bundleIdentifier ?? "")
        if runningApps.count > 1 {
            NSApp.terminate(nil)
        }
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let center = UNUserNotificationCenter.current()
        center.delegate = self
        center.requestAuthorization(options: [.alert, .sound]) { _, _ in }

        DatabaseManager.shared.syncSchedules()
        DatabaseManager.shared.fetchData()
    }

    // Show notifications even when the app is in the foreground (menu bar open)
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound])
    }

    // Handle notification click: bring the running application to the front
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        DispatchQueue.main.async {
            NSApp.activate(ignoringOtherApps: true)
        }
        completionHandler()
    }
}

@main
struct GearboxUIApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var dbManager = DatabaseManager.shared
    @Environment(\.openWindow) var openWindow
    @Environment(\.scenePhase) private var scenePhase
    
    var body: some Scene {
        Window("Gearbox", id: "dashboard") {
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

        Window("Notification Settings", id: "notification-settings") {
            NotificationSettingsView()
        }
        .windowResizability(.contentSize)
    }
}

private enum MenuBarIcon {
    static let appIcon: NSImage = {
        let fallback = NSImage(systemSymbolName: "gearshape.fill", accessibilityDescription: "Gearbox") ?? NSImage()
        guard
            let url = Bundle.main.url(forResource: "AppIcon", withExtension: "icns"),
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
