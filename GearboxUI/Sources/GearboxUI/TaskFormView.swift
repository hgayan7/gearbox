import SwiftUI
import AppKit

struct ScheduleItem: Identifiable, Equatable {
    let id = UUID()
    var frequency: String = "Daily"
    var time: Date = Date()
    var selectedDay: Int = 1
}

struct TaskFormView: View {
    @ObservedObject var dbManager: DatabaseManager
    @Binding var isPresented: Bool
    
    @State private var name: String = ""
    @State private var schedules: [ScheduleItem] = [ScheduleItem()]
    
    @State private var selectedPath: String = ""
    @State private var isDirectory: Bool = false
    @State private var npmScripts: [String] = []
    @State private var selectedNpmCommand: String = ""
    
    @State private var errorMessage: String?
    
    let frequencies = ["Every Minute", "Hourly", "Daily", "Weekdays (Mon-Fri)", "Weekends", "Weekly"]
    let days = [
        ("Monday", 1), ("Tuesday", 2), ("Wednesday", 3),
        ("Thursday", 4), ("Friday", 5), ("Saturday", 6), ("Sunday", 0)
    ]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            VStack(alignment: .leading, spacing: 4) {
                Text("New Automation")
                    .font(.system(size: 18, weight: .bold))
                Text("Schedule a recurring task or script.")
                    .font(.system(size: 12))
                    .foregroundColor(.secondary)
            }
            .padding(24)
            
            Divider()
            
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Name Section
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Name")
                            .font(.system(size: 11, weight: .medium))
                        
                        TextField("Daily Data Backup", text: $name)
                            .textFieldStyle(.roundedBorder)
                    }
                    
                    // Schedule Section
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Schedule")
                            .font(.system(size: 11, weight: .medium))
                        
                        VStack(spacing: 8) {
                            ForEach($schedules) { $schedule in
                                HStack(spacing: 8) {
                                    Picker("", selection: Binding(
                                        get: { schedule.frequency },
                                        set: { newValue in
                                            if let idx = schedules.firstIndex(where: { $0.id == schedule.id }) {
                                                schedules[idx].frequency = newValue
                                                if idx == 0 && (newValue == "Every Minute" || newValue == "Hourly") {
                                                    schedules = [schedules[0]]
                                                }
                                            }
                                        }
                                    )) {
                                        ForEach(frequencies.filter { freq in
                                            if let idx = schedules.firstIndex(where: { $0.id == schedule.id }), idx > 0 {
                                                return freq != "Every Minute" && freq != "Hourly"
                                            }
                                            return true
                                        }, id: \.self) { freq in
                                            Text(freq).tag(freq)
                                        }
                                    }
                                    .frame(width: 130)
                                    
                                    if schedule.frequency == "Weekly" {
                                        Picker("", selection: $schedule.selectedDay) {
                                            ForEach(days, id: \.1) { day in
                                                Text(day.0).tag(day.1)
                                            }
                                        }
                                        .frame(width: 100)
                                    }
                                    
                                    if schedule.frequency != "Every Minute" && schedule.frequency != "Hourly" {
                                        DatePicker("", selection: $schedule.time, displayedComponents: .hourAndMinute)
                                            .datePickerStyle(.stepperField)
                                            .frame(width: 80)
                                    }
                                    
                                    if schedules.count > 1 {
                                        Button(action: {
                                            withAnimation { schedules.removeAll(where: { $0.id == schedule.id }) }
                                        }) {
                                            Image(systemName: "minus.circle.fill")
                                                .foregroundColor(.secondary.opacity(0.8))
                                        }
                                        .buttonStyle(.plain)
                                    }
                                }
                            }
                            
                            if let first = schedules.first, first.frequency != "Every Minute" && first.frequency != "Hourly" {
                                Button(action: {
                                    withAnimation { schedules.append(ScheduleItem()) }
                                }) {
                                    Label("Add execution time", systemImage: "plus")
                                        .font(.system(size: 11))
                                }
                                .buttonStyle(.plain)
                                .foregroundColor(.accentColor)
                                .padding(.top, 4)
                            }
                        }
                        .padding(12)
                        .background(Color.primary.opacity(0.01))
                        .cornerRadius(6)
                    }
                    
                    // Task Action Section
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Action")
                            .font(.system(size: 11, weight: .medium))
                        
                        VStack(alignment: .leading, spacing: 10) {
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(selectedPath.isEmpty ? "Select a script or folder" : (selectedPath as NSString).lastPathComponent)
                                        .font(.system(size: 12, weight: .medium))
                                    if !selectedPath.isEmpty {
                                        Text(selectedPath)
                                            .font(.system(size: 10))
                                            .foregroundColor(.secondary)
                                            .lineLimit(1)
                                            .truncationMode(.middle)
                                    }
                                }
                                
                                Spacer()
                                
                                Button("Choose...") {
                                    // ... panel logic remains the same
                                    let panel = NSOpenPanel()
                                    panel.allowsMultipleSelection = false
                                    panel.canChooseDirectories = true
                                    panel.canChooseFiles = true
                                    if panel.runModal() == .OK, let url = panel.url {
                                        selectedPath = url.path
                                        var isDir: ObjCBool = false
                                        FileManager.default.fileExists(atPath: selectedPath, isDirectory: &isDir)
                                        isDirectory = isDir.boolValue
                                        
                                        if isDirectory {
                                            let packageJsonPath = url.appendingPathComponent("package.json").path
                                            if FileManager.default.fileExists(atPath: packageJsonPath),
                                               let data = try? Data(contentsOf: URL(fileURLWithPath: packageJsonPath)),
                                               let json = try? JSONSerialization.jsonObject(with: data, options: []) as? [String: Any],
                                               let scripts = json["scripts"] as? [String: String] {
                                                npmScripts = Array(scripts.keys).sorted()
                                                if let first = npmScripts.first { selectedNpmCommand = first }
                                            } else {
                                                npmScripts = []
                                            }
                                        } else {
                                            npmScripts = []
                                        }
                                    }
                                }
                                .buttonStyle(.bordered)
                            }
                            
                            if isDirectory && !npmScripts.isEmpty {
                                Picker("NPM Command", selection: $selectedNpmCommand) {
                                    ForEach(npmScripts, id: \.self) { script in
                                        Text("npm run \(script)").tag(script)
                                    }
                                }
                                .pickerStyle(.menu)
                            } else if isDirectory {
                                Text("No package.json or Scripts found in this folder.")
                                    .font(.system(size: 11))
                                    .foregroundColor(GearboxDesign.Color.warning)
                            }
                        }
                        .padding(16)
                        .background(Color.primary.opacity(0.04))
                        .cornerRadius(10)
                    }
                }
                .padding(.horizontal, 30)
            }
            
            Divider().opacity(0.5).padding(.top, 20)
            
            // Footer
            HStack(spacing: 16) {
                if let err = errorMessage {
                    Text(err)
                        .foregroundColor(GearboxDesign.Color.danger)
                        .font(.system(size: 11, weight: .medium))
                }
                
                Spacer()
                
                Button("Cancel") { isPresented = false }
                    .buttonStyle(.plain)
                    .font(.system(size: 13))
                    .foregroundColor(.secondary)
                
                Button("Create Task") { saveTask() }
                    .buttonStyle(.borderedProminent)
                    .tint(GearboxDesign.Color.accent)
                    .disabled(name.isEmpty || selectedPath.isEmpty || (isDirectory && selectedNpmCommand.isEmpty))
            }
            .padding(30)
            .background(Color.primary.opacity(0.02))
        }
        .frame(minHeight: 500)
        .background(Color(nsColor: .windowBackgroundColor))
    }
    
    // ... (rest of the helper functions remain the same)
    private func generateCron(for item: ScheduleItem) -> String {
        let calendar = Calendar.current
        let hour = calendar.component(.hour, from: item.time)
        let minute = calendar.component(.minute, from: item.time)
        
        switch item.frequency {
        case "Every Minute": return "* * * * *"
        case "Hourly": return "0 * * * *"
        case "Daily": return "\(minute) \(hour) * * *"
        case "Weekdays (Mon-Fri)": return "\(minute) \(hour) * * 1-5"
        case "Weekends": return "\(minute) \(hour) * * 0,6"
        case "Weekly": return "\(minute) \(hour) * * \(item.selectedDay)"
        default: return "\(minute) \(hour) * * *"
        }
    }
    
    private func generateCommand() -> String {
        if isDirectory {
            if !npmScripts.isEmpty && !selectedNpmCommand.isEmpty {
                return "cd '\(selectedPath)' && npm run \(selectedNpmCommand)"
            } else {
                return "cd '\(selectedPath)' && echo 'No npm command selected'"
            }
        } else {
            let ext = (selectedPath as NSString).pathExtension.lowercased()
            let dir = (selectedPath as NSString).deletingLastPathComponent
            let base = (selectedPath as NSString).lastPathComponent
            switch ext {
            case "js", "cjs", "mjs": return "cd '\(dir)' && node '\(base)'"
            case "py": return "cd '\(dir)' && python3 '\(base)'"
            case "sh": return "cd '\(dir)' && bash '\(base)'"
            case "applescript": return "cd '\(dir)' && osascript '\(base)'"
            default: return "cd '\(dir)' && open '\(base)'"
            }
        }
    }
    
    private func saveTask() {
        do {
            let safeName = name.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: " ", with: "-")
            let cronList = schedules.map { generateCron(for: $0) }.joined(separator: "|")
            try dbManager.addTaskViaCLI(name: safeName, schedule: cronList, command: generateCommand())
            isPresented = false
        } catch {
            errorMessage = "Name already exists"
        }
    }
}
