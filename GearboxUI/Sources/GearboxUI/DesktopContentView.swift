import SwiftUI

struct DesktopContentView: View {
    @ObservedObject var dbManager: DatabaseManager
    @State private var selectedTaskId: String?
    @State private var showingAddTask = false
    
    let timer = Timer.publish(every: 5, on: .main, in: .common).autoconnect()
    
    var body: some View {
        NavigationSplitView {
            List(selection: $selectedTaskId) {
                Section {
                    if dbManager.tasks.isEmpty {
                        Text("No active automations")
                            .font(.system(size: 11))
                            .foregroundColor(.secondary)
                            .listRowBackground(Color.clear)
                    } else {
                        ForEach(dbManager.tasks) { task in
                            NavigationLink(value: task.id) {
                                TaskListRow(task: task, dbManager: dbManager)
                            }
                        }
                    }
                } header: {
                    Text("Automations")
                }
            }
            .navigationSplitViewColumnWidth(min: 240, ideal: 260)
            .listStyle(.sidebar)
        } detail: {
            if let selectedTaskId = selectedTaskId, let task = dbManager.tasks.first(where: { $0.id == selectedTaskId }) {
                TaskDetailView(task: task, dbManager: dbManager)
            } else {
                DashboardOverviewView(dbManager: dbManager)
            }
        }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button(action: { showingAddTask = true }) {
                    Label("Add Task", systemImage: "plus")
                }
            }
        }
        .sheet(isPresented: $showingAddTask) {
            TaskFormView(dbManager: dbManager, isPresented: $showingAddTask)
                .frame(width: 500)
        }
        .onReceive(timer) { _ in
            dbManager.fetchData()
        }
    }
}

struct TaskListRow: View {
    let task: Task
    @ObservedObject var dbManager: DatabaseManager
    
    var isCurrentlyRunning: Bool { dbManager.activeTaskIds.contains(task.id) }
    
    var body: some View {
        HStack(spacing: 8) {
            if isCurrentlyRunning {
                ProgressView()
                    .controlSize(.small)
                    .scaleEffect(0.5)
                    .frame(width: 14)
            } else {
                Image(systemName: task.isPaused ? "pause.circle" : "play.circle.fill")
                    .font(.system(size: 14))
                    .foregroundColor(task.isPaused ? .secondary : .accentColor)
                    .frame(width: 14)
            }
            
            Text(task.name)
                .font(.system(size: 13, weight: .medium))
        }
        .padding(.vertical, 2)
    }
}

struct DashboardOverviewView: View {
    @ObservedObject var dbManager: DatabaseManager
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "gearshape.fill")
                .font(.system(size: 48))
                .foregroundColor(.secondary.opacity(0.1))
            
            VStack(spacing: 4) {
                Text("Select an automation")
                    .font(.system(size: 16, weight: .semibold))
                Text("View logs and execution history.")
                    .font(.system(size: 13))
                    .foregroundColor(.secondary)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(VisualEffectView(material: .sidebar, blendingMode: .withinWindow))
    }
}

struct TaskDetailView: View {
    let task: Task
    @ObservedObject var dbManager: DatabaseManager
    @State private var runs: [Run] = []
    @State private var selectedRunId: String?
    
    var isCurrentlyRunning: Bool { dbManager.activeTaskIds.contains(task.id) }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            HStack(alignment: .center, spacing: 16) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(task.name)
                        .font(.system(size: 22, weight: .bold))
                    Text(task.scheduleDesc)
                        .font(.system(size: 12))
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                HStack(spacing: 12) {
                    Button(action: {
                        if isCurrentlyRunning {
                            dbManager.stopTaskViaCLI(name: task.name)
                        } else {
                            dbManager.runTaskManually(name: task.name)
                        }
                    }) {
                        Label(isCurrentlyRunning ? "Stop" : "Run Now", systemImage: isCurrentlyRunning ? "stop.fill" : "play.fill")
                            .padding(.horizontal, 4)
                    }
                    .buttonStyle(.bordered)
                    
                    Toggle("", isOn: Binding(
                        get: { !task.isPaused },
                        set: { _ in dbManager.togglePause(task: task) }
                    ))
                    .toggleStyle(.switch)
                    .labelsHidden()
                    .controlSize(.small)
                }
            }
            .padding(24)
            .background(VisualEffectView(material: .titlebar, blendingMode: .withinWindow))
            
            Divider()
            
            VSplitView {
                VStack(alignment: .leading, spacing: 0) {
                    Table(runs, selection: $selectedRunId) {
                        TableColumn("Status") { run in
                            Label(run.status.capitalized, 
                                  systemImage: run.status == "success" ? "checkmark.circle" : "xmark.circle")
                                .foregroundColor(run.status == "success" ? .secondary : .red.opacity(0.8))
                        }
                        .width(100)
                        
                        TableColumn("Started At") { run in
                            Text(run.startedAt)
                                .font(.system(size: 11))
                                .foregroundColor(.secondary)
                        }
                    }
                }
                .frame(minHeight: 150)
                
                if let id = selectedRunId, let run = runs.first(where: { $0.id == id }) {
                    RunDetailView(run: run)
                        .frame(minHeight: 200)
                } else {
                    VStack {
                        Text("Select an execution to view logs")
                            .font(.system(size: 12))
                            .foregroundColor(.secondary.opacity(0.5))
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color(nsColor: .textBackgroundColor))
                }
            }
        }
        .onAppear { refreshRuns() }
        .onChange(of: task.id) { _ in refreshRuns() }
        .onReceive(Timer.publish(every: 5, on: .main, in: .common).autoconnect()) { _ in refreshRuns() }
    }
    
    private func refreshRuns() {
        runs = dbManager.fetchRuns(for: task.id)
    }
}
