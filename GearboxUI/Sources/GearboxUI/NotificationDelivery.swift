import SwiftUI
import UserNotifications

// Extension on DatabaseManager to handle all UNUserNotificationCenter calls.
// Kept in a separate file to ensure the UserNotifications framework is fully
// bridged at compile time (the types are otherwise unavailable in Database.swift
// despite the import, due to Swift package framework bridging order).
extension DatabaseManager {
    func postRunNotification(runId: String, taskName: String, status: String, exitCode: Int) {
        let content = UNMutableNotificationContent()
        content.title = "Gearbox"
        content.sound = .default

        switch status {
        case "success":
            content.body = "\u{2705} \(taskName) completed successfully"
            content.categoryIdentifier = "GEARBOX_RUN_SUCCESS"
        case "failed":
            content.body = "\u{274C} \(taskName) failed (exit \(exitCode))"
            content.categoryIdentifier = "GEARBOX_RUN_FAILED"
        default:
            return
        }

        content.userInfo = [
            "runId": runId,
            "taskName": taskName,
            "status": status,
            "exitCode": exitCode
        ]

        let request = UNNotificationRequest(
            identifier: runId,
            content: content,
            trigger: nil
        )
        UNUserNotificationCenter.current().add(request) { error in
            if let error { print("[Gearbox] Notification error: \(error)") }
        }
    }
}
