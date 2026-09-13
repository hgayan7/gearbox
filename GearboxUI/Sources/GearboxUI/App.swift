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

        let retryAction = UNNotificationAction(
            identifier: "ACTION_RETRY",
            title: "Retry Now",
            options: [.foreground]
        )
        let viewLogsAction = UNNotificationAction(
            identifier: "ACTION_VIEW_LOGS",
            title: "View Logs",
            options: [.foreground]
        )
        let failedCategory = UNNotificationCategory(
            identifier: "GEARBOX_RUN_FAILED",
            actions: [retryAction, viewLogsAction],
            intentIdentifiers: [],
            options: [.customDismissAction]
        )
        let successCategory = UNNotificationCategory(
            identifier: "GEARBOX_RUN_SUCCESS",
            actions: [viewLogsAction],
            intentIdentifiers: [],
            options: []
        )
        center.setNotificationCategories([failedCategory, successCategory])

        DatabaseManager.shared.syncSchedules()
        DatabaseManager.shared.fetchData()
        WebhookServer.shared.start()
    }

    // Show notifications even when the app is in the foreground (menu bar open)
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound])
    }

    // Handle notification clicks and actions
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        let userInfo = response.notification.request.content.userInfo
        let taskName = userInfo["taskName"] as? String

        if response.actionIdentifier == "ACTION_RETRY", let taskName = taskName {
            DatabaseManager.shared.runTaskManually(name: taskName)
        } else {
            DispatchQueue.main.async {
                NSApp.activate(ignoringOtherApps: true)
            }
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
                .onOpenURL { url in
                    guard url.scheme?.lowercased() == "gearbox" else { return }
                    if url.host == "run" {
                        let taskName = url.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
                        if !taskName.isEmpty {
                            DatabaseManager.shared.runTaskManually(name: taskName)
                        }
                    }
                }
        }
        
        MenuBarExtra {
            MenuBarContentView(dbManager: dbManager)
        } label: {
            HStack(spacing: 3) {
                if dbManager.hasActiveRun {
                    Image(systemName: "arrow.triangle.2.circlepath.circle.fill")
                } else {
                    Image(nsImage: MenuBarIcon.appIcon)
                }
                if dbManager.recentFailureCount > 0 {
                    Circle()
                        .fill(Color.red)
                        .frame(width: 5, height: 5)
                }
            }
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
