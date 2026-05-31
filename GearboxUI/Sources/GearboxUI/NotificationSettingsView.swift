import SwiftUI
import UserNotifications

struct NotificationSettingsView: View {
    @AppStorage("gearbox.notify.success") private var notifyOnSuccess: Bool = false
    @AppStorage("gearbox.notify.failure") private var notifyOnFailure: Bool = true

    @State private var authStatus: UNAuthorizationStatus = .notDetermined

    var body: some View {
        Form {
            // MARK: - Triggers
            Section {
                HStack {
                    notificationIcon(systemName: "checkmark.circle.fill", color: .green)
                    Toggle("Notify when a task succeeds", isOn: $notifyOnSuccess)
                        .disabled(authStatus == .denied)
                }

                HStack {
                    notificationIcon(systemName: "xmark.circle.fill", color: .red)
                    Toggle("Notify when a task fails", isOn: $notifyOnFailure)
                        .disabled(authStatus == .denied)
                }
            } header: {
                Text("Task Completion")
            } footer: {
                Text("Cancelled tasks never trigger a notification.")
                    .foregroundColor(.secondary)
            }

            // MARK: - Permission
            Section {
                HStack(spacing: 8) {
                    Text("macOS Permission")
                    Spacer()
                    permissionBadge
                }

                if authStatus == .denied {
                    Button {
                        NSWorkspace.shared.open(
                            URL(string: "x-apple.systempreferences:com.apple.preference.notifications")!
                        )
                    } label: {
                        Label("Open System Notification Settings", systemImage: "arrow.up.right.square")
                    }
                }
            } header: {
                Text("System")
            } footer: {
                if authStatus == .denied {
                    Text("Gearbox has been denied notification access. Enable it in System Settings to receive alerts.")
                        .foregroundColor(.red.opacity(0.8))
                }
            }
        }
        .formStyle(.grouped)
        .frame(width: 400)
        .fixedSize()
        .onAppear(perform: refreshPermissionStatus)
        .onChange(of: notifyOnSuccess) { _ in refreshPermissionStatus() }
        .onChange(of: notifyOnFailure) { _ in refreshPermissionStatus() }
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.didBecomeActiveNotification)) { _ in
            refreshPermissionStatus()
        }
    }

    // MARK: - Sub-views

    private func notificationIcon(systemName: String, color: Color) -> some View {
        Image(systemName: systemName)
            .font(.system(size: 14))
            .foregroundColor(color)
            .frame(width: 20)
    }

    @ViewBuilder
    private var permissionBadge: some View {
        switch authStatus {
        case .authorized, .provisional:
            Label("Authorized", systemImage: "checkmark.circle.fill")
                .foregroundColor(.green)
                .font(.system(size: 12, weight: .medium))
        case .denied:
            Label("Denied", systemImage: "xmark.circle.fill")
                .foregroundColor(.red)
                .font(.system(size: 12, weight: .medium))
        case .notDetermined:
            Label("Not requested", systemImage: "questionmark.circle")
                .foregroundColor(.secondary)
                .font(.system(size: 12, weight: .medium))
        @unknown default:
            Label("Unknown", systemImage: "questionmark.circle")
                .foregroundColor(.secondary)
                .font(.system(size: 12, weight: .medium))
        }
    }

    // MARK: - Helpers

    private func refreshPermissionStatus() {
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            DispatchQueue.main.async {
                authStatus = settings.authorizationStatus
            }
        }
    }
}
