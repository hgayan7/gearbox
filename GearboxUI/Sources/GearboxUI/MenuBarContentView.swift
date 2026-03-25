import SwiftUI

struct MenuBarContentView: View {
    @ObservedObject var dbManager: DatabaseManager
    @Environment(\.openWindow) var openWindow
    
    let timer = Timer.publish(every: 5, on: .main, in: .common).autoconnect()
    
    var allPaused: Bool {
        dbManager.tasks.allSatisfy { $0.isPaused }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Native Header
            HStack {
                VStack(alignment: .leading, spacing: 1) {
                    HStack(spacing: 6) {
                        Image(systemName: "gearshape.fill")
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundColor(.accentColor)
                        Text("Gearbox")
                            .font(.system(size: 16, weight: .bold))
                    }
                    Text("AUTOMATION")
                        .font(.system(size: 8, weight: .semibold))
                        .kerning(0.8)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                HStack(spacing: 8) {
                    Button(action: {
                        openWindow(id: "dashboard")
                        NSApp.activate(ignoringOtherApps: true)
                    }) {
                        Image(systemName: "macwindow")
                            .font(.system(size: 13))
                    }
                    .buttonStyle(.plain)
                    
                    Button(action: {
                        NSApplication.shared.terminate(nil)
                    }) {
                        Image(systemName: "power")
                            .font(.system(size: 13))
                            .foregroundColor(.secondary)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 14)
            .background(VisualEffectView(material: .popover, blendingMode: .withinWindow))
            
            Divider()
            
            // Engine Status
            HStack {
                Text(allPaused ? "System Paused" : "System Active")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundColor(.secondary)
                
                Spacer()
                
                Button(allPaused ? "Resume All" : "Pause All") {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        for task in dbManager.tasks {
                            if task.isPaused != allPaused {
                                dbManager.togglePause(task: task)
                            }
                        }
                    }
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(Color.primary.opacity(0.02))
            
            Divider()
            
            // Tasks Section
            VStack(alignment: .leading, spacing: 4) {
                if dbManager.tasks.isEmpty {
                    Text("No active automations")
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 30)
                } else {
                    ScrollView {
                        VStack(spacing: 0) {
                            ForEach(dbManager.tasks) { task in
                                MenuBarTaskRow(task: task, dbManager: dbManager)
                                if task.id != dbManager.tasks.last?.id {
                                    Divider().padding(.leading, 40).opacity(0.5)
                                }
                            }
                        }
                    }
                    .frame(maxHeight: 280)
                }
            }
            
            Divider()
            
            // Latest Activity
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("LATEST ACTIVITY")
                        .font(.system(size: 9, weight: .semibold))
                        .foregroundColor(.secondary)
                    Spacer()
                    Button(action: { dbManager.fetchData() }) {
                        Image(systemName: "arrow.clockwise")
                            .font(.system(size: 9))
                    }
                    .buttonStyle(.plain)
                    .foregroundColor(.secondary.opacity(0.5))
                }
                
                if dbManager.recentRuns.isEmpty {
                    Text("No recent activity")
                        .font(.system(size: 10))
                        .foregroundColor(.secondary.opacity(0.5))
                        .padding(.vertical, 2)
                } else {
                    VStack(spacing: 6) {
                        ForEach(dbManager.recentRuns.prefix(2), id: \.id) { run in
                            let config = statusConfig(for: run.status)
                            HStack(spacing: 8) {
                                Image(systemName: config.icon)
                                    .font(.system(size: 10))
                                    .foregroundColor(config.color)
                                
                                let taskName = dbManager.tasks.first(where: { $0.id == run.taskId })?.name ?? "Event"
                                Text(taskName)
                                    .font(.system(size: 10, weight: .medium))
                                    .lineLimit(1)
                                
                                Spacer()
                                
                                Text(run.startedAt.split(separator: " ").last ?? "")
                                    .font(.system(size: 9))
                                    .foregroundColor(.secondary.opacity(0.6))
                            }
                        }
                    }
                }
            }
            .padding(16)
            .background(Color.primary.opacity(0.01))
        }
        .frame(width: 280)
        .onReceive(timer) { _ in
            dbManager.fetchData()
        }
    }
    
    private func statusConfig(for status: String) -> (icon: String, color: Color) {
        switch status.lowercased() {
        case "running": return ("circle.dashed", .blue)
        case "success": return ("checkmark.circle", .secondary)
        case "failed": return ("xmark.circle", .red.opacity(0.7))
        case "cancelled": return ("minus.circle", .gray)
        default: return ("questionmark.circle", .secondary)
        }
    }
}

struct MenuBarTaskRow: View {
    let task: Task
    @ObservedObject var dbManager: DatabaseManager
    
    var isCurrentlyRunning: Bool { dbManager.activeTaskIds.contains(task.id) }
    
    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                if isCurrentlyRunning {
                    ProgressView()
                        .controlSize(.small)
                        .scaleEffect(0.5)
                } else {
                    Image(systemName: task.isPaused ? "pause.circle" : "play.circle.fill")
                        .font(.system(size: 14))
                        .foregroundColor(task.isPaused ? .secondary : .accentColor)
                }
            }
            .frame(width: 16)
            
            VStack(alignment: .leading, spacing: 1) {
                Text(task.name)
                    .font(.system(size: 13, weight: .medium))
                Text(task.scheduleDesc)
                    .font(.system(size: 10))
                    .foregroundColor(.secondary)
            }
            .help(task.command)
            
            Spacer()
            
            Toggle("", isOn: Binding(
                get: { !task.isPaused },
                set: { _ in dbManager.togglePause(task: task) }
            ))
            .toggleStyle(.switch)
            .scaleEffect(0.6)
            .labelsHidden()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .contentShape(Rectangle())
    }
}

struct VisualEffectView: NSViewRepresentable {
    let material: NSVisualEffectView.Material
    let blendingMode: NSVisualEffectView.BlendingMode
    
    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.material = material
        view.blendingMode = blendingMode
        view.state = .active
        return view
    }
    
    func updateNSView(_ nsView: NSVisualEffectView, context: Context) {
        nsView.material = material
        nsView.blendingMode = blendingMode
    }
}
