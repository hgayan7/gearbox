import SwiftUI
import AppKit

struct TaskFormView: View {
    @ObservedObject var dbManager: DatabaseManager
    @Binding var isPresented: Bool

    let mode: TaskEditorMode

    @State private var name: String
    @State private var triggerType: TaskTriggerType
    @State private var watchPath: String
    @State private var scheduleMode: TaskScheduleMode
    @State private var schedules: [ScheduleItem]
    @State private var customCronSchedule: String

    @State private var executionMode: TaskExecutionMode
    @State private var selectedPath: String
    @State private var isDirectory: Bool
    @State private var npmScripts: [String]
    @State private var selectedNpmCommand: String
    @State private var customCommand: String
    @State private var workingDirectory: String
    @State private var shellPath: String
    @State private var environmentRows: [EnvironmentVariableRow]

    @State private var timeoutSeconds: Int
    @State private var requiresAcPower: Bool
    @State private var preventSleep: Bool
    @State private var maxRetries: Int
    @State private var retryDelaySeconds: Int
    @State private var onSuccessTaskId: String
    @State private var onFailureTaskId: String

    @State private var schedulePreview: SchedulePreview?
    @State private var schedulePreviewError: String?
    @State private var errorMessage: String?

    private let frequencies = ["Hourly", "Daily", "Weekdays (Mon-Fri)", "Weekends", "Weekly"]
    private let days = [
        ("Monday", 1), ("Tuesday", 2), ("Wednesday", 3),
        ("Thursday", 4), ("Friday", 5), ("Saturday", 6), ("Sunday", 0)
    ]

    init(dbManager: DatabaseManager, isPresented: Binding<Bool>, mode: TaskEditorMode = .create) {
        self.dbManager = dbManager
        self._isPresented = isPresented
        self.mode = mode

        let task = mode.existingTask
        let inferredExecution = TaskEditorParser.inferExecutionSettings(
            command: task?.command ?? "",
            rawCommand: task?.rawCommand,
            workingDirectory: task?.workingDirectory
        )
        let presetSchedules = task.flatMap { TaskEditorParser.parsePresetSchedules(schedule: $0.schedule) } ?? [ScheduleItem()]

        self._name = State(initialValue: task?.name ?? "")
        self._triggerType = State(initialValue: TaskTriggerType.from(storageValue: task?.triggerType))
        self._watchPath = State(initialValue: task?.watchPath ?? "")
        self._scheduleMode = State(initialValue: task.flatMap { TaskEditorParser.parsePresetSchedules(schedule: $0.schedule) } == nil ? .customCron : .preset)
        self._schedules = State(initialValue: presetSchedules)
        self._customCronSchedule = State(initialValue: task?.schedule ?? "")
        self._executionMode = State(initialValue: task == nil ? .guided : .command)
        self._selectedPath = State(initialValue: "")
        self._isDirectory = State(initialValue: false)
        self._npmScripts = State(initialValue: [])
        self._selectedNpmCommand = State(initialValue: "")
        self._customCommand = State(initialValue: inferredExecution.rawCommand)
        self._workingDirectory = State(initialValue: inferredExecution.workingDirectory ?? "")
        self._shellPath = State(initialValue: task?.shell ?? "/bin/zsh")
        self._environmentRows = State(initialValue: TaskEditorParser.environmentRows(from: task?.environment ?? [:]))
        self._timeoutSeconds = State(initialValue: task?.timeoutSeconds ?? 0)
        self._requiresAcPower = State(initialValue: task?.requiresAcPower ?? false)
        self._preventSleep = State(initialValue: task?.preventSleep ?? false)
        self._maxRetries = State(initialValue: task?.maxRetries ?? 0)
        self._retryDelaySeconds = State(initialValue: task?.retryDelaySeconds ?? 10)
        self._onSuccessTaskId = State(initialValue: task?.onSuccessTaskId ?? "")
        self._onFailureTaskId = State(initialValue: task?.onFailureTaskId ?? "")
        self._schedulePreview = State(initialValue: nil)
        self._schedulePreviewError = State(initialValue: nil)
        self._errorMessage = State(initialValue: nil)
    }

    private var canSave: Bool {
        if trimmedName.isEmpty || resolvedCommandValidationError != nil {
            return false
        }
        if triggerType == .fileWatch && watchPath.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return false
        }
        return true
    }

    private var trimmedName: String {
        name.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var scheduleInputForPreview: String {
        switch scheduleMode {
        case .preset:
            return schedules.map { generateCron(for: $0) }.joined(separator: " | ")
        case .customCron:
            return customCronSchedule.trimmingCharacters(in: .whitespacesAndNewlines)
        }
    }

    private var resolvedCommandValidationError: String? {
        switch executionMode {
        case .guided:
            if selectedPath.isEmpty {
                return "Choose a script or folder."
            }
            if isDirectory && selectedNpmCommand.isEmpty {
                return "Choose an npm script or use Custom Command."
            }
            return nil
        case .command:
            return TaskEditorParser.normalizedText(customCommand) == nil ? "Enter a command to run." : nil
        }
    }

    private var filteredEnvironment: [String: String] {
        environmentRows.reduce(into: [String: String]()) { partialResult, row in
            let key = row.key.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !key.isEmpty else { return }
            partialResult[key] = row.value
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            headerSection

            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    nameSection
                    triggerSection
                    executionSection
                    safetySection
                    resilienceSection
                    environmentSection
                    resolvedCommandSection
                }
                .padding(.horizontal, 30)
                .padding(.vertical, 24)
            }

            Divider().opacity(0.5)

            footerSection
        }
        .frame(minWidth: 640, minHeight: 620)
        .background(Color(nsColor: .windowBackgroundColor))
        .onAppear {
            refreshSchedulePreview()
        }
        .onChange(of: scheduleMode) { _ in
            refreshSchedulePreview()
        }
        .onChange(of: schedules) { _ in
            refreshSchedulePreview()
        }
        .onChange(of: customCronSchedule) { _ in
            refreshSchedulePreview()
        }
    }

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(mode.title)
                .font(.system(size: 18, weight: .bold))
            Text(mode.subtitle)
                .font(.system(size: 12))
                .foregroundStyle(.secondary)
        }
        .padding(24)
    }

    private var nameSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Name")
                .font(.system(size: 11, weight: .medium))

            TextField("Daily Data Backup", text: $name)
                .textFieldStyle(.roundedBorder)
        }
    }

    private var triggerSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Trigger")
                .font(.system(size: 11, weight: .medium))

            Picker("Trigger Type", selection: $triggerType) {
                ForEach(TaskTriggerType.allCases) { type in
                    Text(type.rawValue).tag(type)
                }
            }
            .pickerStyle(.segmented)

            switch triggerType {
            case .cron:
                scheduleSection
            case .fileWatch:
                folderWatchSection
            }
        }
    }

    private var folderWatchSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Watch Directory")
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(.secondary)

            HStack(spacing: 8) {
                TextField("e.g. /Users/name/Downloads", text: $watchPath)
                    .textFieldStyle(.roundedBorder)

                Button("Choose Folder...") {
                    chooseWatchFolder()
                }
            }

            Text("Gearbox will automatically execute this automation whenever files are created or modified in this folder.")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
        }
        .padding(14)
        .background(Color.primary.opacity(0.02))
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }

    private func chooseWatchFolder() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true

        guard panel.runModal() == .OK, let url = panel.url else { return }
        watchPath = url.path
    }

    private var scheduleSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Schedule")
                .font(.system(size: 11, weight: .medium))

            Picker("Schedule Mode", selection: $scheduleMode) {
                ForEach(TaskScheduleMode.allCases) { scheduleMode in
                    Text(scheduleMode.rawValue).tag(scheduleMode)
                }
            }
            .pickerStyle(.segmented)

            Group {
                switch scheduleMode {
                case .preset:
                    presetScheduleEditor
                case .customCron:
                    customCronEditor
                }
            }

            schedulePreviewSection
        }
    }

    private var presetScheduleEditor: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach($schedules) { $schedule in
                HStack(spacing: 8) {
                    Picker("", selection: Binding(
                        get: { schedule.frequency },
                        set: { newValue in
                            if let index = schedules.firstIndex(where: { $0.id == schedule.id }) {
                                schedules[index].frequency = newValue
                                if index == 0 && newValue == "Hourly" {
                                    schedules = [schedules[0]]
                                }
                            }
                        }
                    )) {
                        ForEach(frequencies.filter { frequency in
                            if let index = schedules.firstIndex(where: { $0.id == schedule.id }), index > 0 {
                                return frequency != "Hourly"
                            }
                            return true
                        }, id: \.self) { frequency in
                            Text(frequency).tag(frequency)
                        }
                    }
                    .frame(width: 150)

                    if schedule.frequency == "Weekly" {
                        Picker("", selection: $schedule.selectedDay) {
                            ForEach(days, id: \.1) { day in
                                Text(day.0).tag(day.1)
                            }
                        }
                        .frame(width: 110)
                    }

                    if schedule.frequency != "Hourly" {
                        DatePicker("", selection: $schedule.time, displayedComponents: .hourAndMinute)
                            .datePickerStyle(.stepperField)
                            .frame(width: 92)
                    }

                    if schedules.count > 1 {
                        Button {
                            withAnimation {
                                schedules.removeAll { $0.id == schedule.id }
                            }
                        } label: {
                            Image(systemName: "minus.circle.fill")
                                .foregroundStyle(.secondary)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }

            if schedules.first?.frequency != "Hourly" {
                Button {
                    withAnimation {
                        schedules.append(ScheduleItem())
                    }
                } label: {
                    Label("Add execution time", systemImage: "plus")
                        .font(.system(size: 11))
                }
                .buttonStyle(.plain)
                .foregroundStyle(Color.accentColor)
            }
        }
        .padding(14)
        .background(Color.primary.opacity(0.03))
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }

    private var customCronEditor: some View {
        VStack(alignment: .leading, spacing: 8) {
            TextField("Examples: 0 9 * * 1-5 | 30 18 * * *", text: $customCronSchedule)
                .textFieldStyle(.roundedBorder)

            Text("Multiple schedules can be separated with `|`.")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
        }
    }

    private var schedulePreviewSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Preview")
                    .font(.system(size: 11, weight: .medium))
                Spacer()
                if let schedulePreview {
                    Text(schedulePreview.timezone)
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
            }

            if let schedulePreview {
                VStack(alignment: .leading, spacing: 8) {
                    Text(schedulePreview.description)
                        .font(.system(size: 12, weight: .medium))

                    Text(schedulePreview.normalizedSchedule)
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(.secondary)

                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(Array(schedulePreview.nextRuns.prefix(3)), id: \.self) { nextRun in
                            Text(previewDateLabel(for: nextRun))
                                .font(.system(size: 11))
                                .foregroundStyle(.secondary)
                        }
                    }
                }
                .padding(14)
                .background(Color.primary.opacity(0.03))
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            } else if let schedulePreviewError {
                Text(schedulePreviewError)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(.red)
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.red.opacity(0.07))
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            } else {
                Text("Enter a schedule to preview the next runs.")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.primary.opacity(0.03))
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            }
        }
    }

    private var executionSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Action")
                .font(.system(size: 11, weight: .medium))

            Picker("Execution Mode", selection: $executionMode) {
                ForEach(TaskExecutionMode.allCases) { executionMode in
                    Text(executionMode.rawValue).tag(executionMode)
                }
            }
            .pickerStyle(.segmented)

            Group {
                switch executionMode {
                case .guided:
                    guidedExecutionSection
                case .command:
                    customCommandSection
                }
            }
        }
    }

    private var guidedExecutionSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(selectedPath.isEmpty ? "Select a script or folder" : (selectedPath as NSString).lastPathComponent)
                        .font(.system(size: 12, weight: .medium))
                    if !selectedPath.isEmpty {
                        Text(selectedPath)
                            .font(.system(size: 10))
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                            .truncationMode(.middle)
                    }
                }

                Spacer()

                Button("Choose...") {
                    chooseGuidedPath()
                }
                .buttonStyle(.bordered)
            }

            if isDirectory && !npmScripts.isEmpty {
                Picker("NPM Script", selection: $selectedNpmCommand) {
                    ForEach(npmScripts, id: \.self) { script in
                        Text("npm run \(script)").tag(script)
                    }
                }
                .pickerStyle(.menu)
            } else if isDirectory {
                Text("No npm scripts found in this folder. Switch to Custom Command if you want another command.")
                    .font(.system(size: 11))
                    .foregroundStyle(.orange)
            }
        }
        .padding(16)
        .background(Color.primary.opacity(0.04))
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }

    private var customCommandSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 6) {
                Text("Command")
                    .font(.system(size: 11, weight: .medium))
                TextEditor(text: $customCommand)
                    .font(.system(size: 12, design: .monospaced))
                    .frame(minHeight: 110)
                    .padding(8)
                    .background(Color.primary.opacity(0.03))
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("Working Directory")
                    .font(.system(size: 11, weight: .medium))
                TextField("/path/to/project", text: $workingDirectory)
                    .textFieldStyle(.roundedBorder)
            }
        }
    }

    private var environmentSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Execution Environment")
                .font(.system(size: 11, weight: .medium))

            VStack(alignment: .leading, spacing: 12) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Shell")
                        .font(.system(size: 11, weight: .medium))
                    TextField("/bin/zsh", text: $shellPath)
                        .textFieldStyle(.roundedBorder)
                }

                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text("Environment Variables")
                            .font(.system(size: 11, weight: .medium))
                        Spacer()
                        Button {
                            environmentRows.append(EnvironmentVariableRow())
                        } label: {
                            Label("Add Variable", systemImage: "plus")
                                .font(.system(size: 11))
                        }
                        .buttonStyle(.plain)
                    }

                    if environmentRows.isEmpty {
                        Text("No custom environment variables.")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach($environmentRows) { $row in
                            HStack(spacing: 8) {
                                TextField("KEY", text: $row.key)
                                    .textFieldStyle(.roundedBorder)
                                TextField("value", text: $row.value)
                                    .textFieldStyle(.roundedBorder)
                                Button {
                                    environmentRows.removeAll { $0.id == row.id }
                                } label: {
                                    Image(systemName: "minus.circle.fill")
                                        .foregroundStyle(.secondary)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                }
            }
            .padding(16)
            .background(Color.primary.opacity(0.04))
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        }
    }

    private var safetySection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Execution Safety & Battery")
                .font(.system(size: 11, weight: .medium))

            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Timeout (seconds):")
                        .font(.system(size: 12))
                    Spacer()
                    TextField("0 for unlimited", value: $timeoutSeconds, formatter: NumberFormatter())
                        .frame(width: 100)
                        .textFieldStyle(.roundedBorder)
                }

                Divider()

                Toggle(isOn: $requiresAcPower) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Require AC Power")
                            .font(.system(size: 12, weight: .medium))
                        Text("Skip execution when running on MacBook battery to preserve power.")
                            .font(.system(size: 10))
                            .foregroundStyle(.secondary)
                    }
                }
                .toggleStyle(.checkbox)

                Divider()

                Toggle(isOn: $preventSleep) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Prevent Sleep While Running (Caffeinate)")
                            .font(.system(size: 12, weight: .medium))
                        Text("Keeps the Mac awake until the automation finishes executing.")
                            .font(.system(size: 10))
                            .foregroundStyle(.secondary)
                    }
                }
                .toggleStyle(.checkbox)
            }
            .padding(14)
            .background(Color.primary.opacity(0.02))
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        }
    }

    private var resilienceSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Workflows & Retries")
                .font(.system(size: 11, weight: .medium))

            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Max Retries on Failure:")
                        .font(.system(size: 12))
                    Spacer()
                    Picker("", selection: $maxRetries) {
                        Text("None (0)").tag(0)
                        Text("1 retry").tag(1)
                        Text("2 retries").tag(2)
                        Text("3 retries").tag(3)
                        Text("5 retries").tag(5)
                    }
                    .frame(width: 130)
                }

                if maxRetries > 0 {
                    HStack {
                        Text("Retry Delay (seconds):")
                            .font(.system(size: 12))
                        Spacer()
                        TextField("Seconds", value: $retryDelaySeconds, formatter: NumberFormatter())
                            .frame(width: 100)
                            .textFieldStyle(.roundedBorder)
                    }
                }

                Divider()

                HStack {
                    Text("On Success, run:")
                        .font(.system(size: 12))
                    Spacer()
                    Picker("", selection: $onSuccessTaskId) {
                        Text("None").tag("")
                        ForEach(dbManager.tasks.filter { $0.name != trimmedName }) { t in
                            Text(t.name).tag(t.id)
                        }
                    }
                    .frame(width: 160)
                }

                HStack {
                    Text("On Failure, run:")
                        .font(.system(size: 12))
                    Spacer()
                    Picker("", selection: $onFailureTaskId) {
                        Text("None").tag("")
                        ForEach(dbManager.tasks.filter { $0.name != trimmedName }) { t in
                            Text(t.name).tag(t.id)
                        }
                    }
                    .frame(width: 160)
                }
            }
            .padding(14)
            .background(Color.primary.opacity(0.02))
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        }
    }

    private var resolvedCommandSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Resolved Command")
                .font(.system(size: 11, weight: .medium))

            if let resolvedExecution = try? resolvedExecution() {
                VStack(alignment: .leading, spacing: 6) {
                    if let workingDirectory = resolvedExecution.workingDirectory {
                        Text("Working directory: \(workingDirectory)")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                    }
                    Text(resolvedExecution.displayCommand)
                        .font(.system(size: 11, design: .monospaced))
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding(14)
                .background(Color.primary.opacity(0.03))
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            } else if let resolvedCommandValidationError {
                Text(resolvedCommandValidationError)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(.red)
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.red.opacity(0.07))
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            }
        }
    }

    private var footerSection: some View {
        HStack(spacing: 16) {
            if let errorMessage {
                Text(errorMessage)
                    .foregroundStyle(.red)
                    .font(.system(size: 11, weight: .medium))
            }

            Spacer()

            Button("Cancel") {
                isPresented = false
            }
            .buttonStyle(.plain)
            .font(.system(size: 13))
            .foregroundStyle(.secondary)

            Button(mode.primaryButtonTitle) {
                saveTask()
            }
            .buttonStyle(.borderedProminent)
            .disabled(!canSave)
        }
        .padding(24)
        .background(Color.primary.opacity(0.02))
    }

    private func chooseGuidedPath() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = true
        panel.canChooseFiles = true

        guard panel.runModal() == .OK, let url = panel.url else { return }

        selectedPath = url.path
        var isDir: ObjCBool = false
        FileManager.default.fileExists(atPath: selectedPath, isDirectory: &isDir)
        isDirectory = isDir.boolValue

        if isDirectory {
            let packageJSONPath = url.appendingPathComponent("package.json")
            guard
                FileManager.default.fileExists(atPath: packageJSONPath.path),
                let data = try? Data(contentsOf: packageJSONPath),
                let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                let scripts = json["scripts"] as? [String: String]
            else {
                npmScripts = []
                selectedNpmCommand = ""
                return
            }

            npmScripts = Array(scripts.keys).sorted()
            if !npmScripts.contains(selectedNpmCommand) {
                selectedNpmCommand = npmScripts.first ?? ""
            }
        } else {
            npmScripts = []
            selectedNpmCommand = ""
        }
    }

    private func generateCron(for item: ScheduleItem) -> String {
        let calendar = Calendar.current
        let hour = calendar.component(.hour, from: item.time)
        let minute = calendar.component(.minute, from: item.time)

        switch item.frequency {
        case "Hourly":
            return "0 * * * *"
        case "Daily":
            return "\(minute) \(hour) * * *"
        case "Weekdays (Mon-Fri)":
            return "\(minute) \(hour) * * 1-5"
        case "Weekends":
            return "\(minute) \(hour) * * 0,6"
        case "Weekly":
            return "\(minute) \(hour) * * \(item.selectedDay)"
        default:
            return "\(minute) \(hour) * * *"
        }
    }

    private func resolvedExecution() throws -> (rawCommand: String, workingDirectory: String?, displayCommand: String) {
        switch executionMode {
        case .guided:
            guard !selectedPath.isEmpty else {
                throw ValidationError("Choose a script or folder.")
            }

            if isDirectory {
                guard !selectedNpmCommand.isEmpty else {
                    throw ValidationError("Choose an npm script or use Custom Command.")
                }
                let rawCommand = "npm run \(selectedNpmCommand)"
                let displayCommand = "cd '\(selectedPath)' && \(rawCommand)"
                return (rawCommand, selectedPath, displayCommand)
            }

            let fileURL = URL(fileURLWithPath: selectedPath)
            let directory = fileURL.deletingLastPathComponent().path
            let fileName = fileURL.lastPathComponent
            let rawCommand: String

            switch fileURL.pathExtension.lowercased() {
            case "js", "cjs", "mjs":
                rawCommand = "node '\(fileName)'"
            case "py":
                rawCommand = "python3 '\(fileName)'"
            case "sh":
                rawCommand = "bash '\(fileName)'"
            case "applescript":
                rawCommand = "osascript '\(fileName)'"
            default:
                rawCommand = "open '\(fileName)'"
            }

            return (rawCommand, directory, "cd '\(directory)' && \(rawCommand)")

        case .command:
            guard let rawCommand = TaskEditorParser.normalizedText(customCommand) else {
                throw ValidationError("Enter a command to run.")
            }

            let normalizedWorkingDirectory = TaskEditorParser.normalizedText(workingDirectory)
            let displayCommand: String
            if let normalizedWorkingDirectory {
                displayCommand = "cd '\(normalizedWorkingDirectory)' && \(rawCommand)"
            } else {
                displayCommand = rawCommand
            }
            return (rawCommand, normalizedWorkingDirectory, displayCommand)
        }
    }

    private func resolvedSchedule() throws -> String {
        guard let schedulePreview else {
            throw ValidationError(schedulePreviewError ?? "Enter a valid schedule.")
        }
        return schedulePreview.normalizedSchedule
    }

    private func refreshSchedulePreview() {
        let scheduleInput = scheduleInputForPreview
        guard !scheduleInput.isEmpty else {
            schedulePreview = nil
            schedulePreviewError = nil
            return
        }

        do {
            schedulePreview = try dbManager.previewSchedule(scheduleInput)
            schedulePreviewError = nil
        } catch {
            schedulePreview = nil
            schedulePreviewError = error.localizedDescription
        }
    }

    private func previewDateLabel(for isoString: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

        let fallbackFormatter = ISO8601DateFormatter()
        fallbackFormatter.formatOptions = [.withInternetDateTime]

        let displayFormatter = DateFormatter()
        displayFormatter.dateStyle = .medium
        displayFormatter.timeStyle = .short

        if let date = formatter.date(from: isoString) ?? fallbackFormatter.date(from: isoString) {
            return displayFormatter.string(from: date)
        }
        return isoString
    }

    private func saveTask() {
        errorMessage = nil

        do {
            let resolvedExecution = try resolvedExecution()
            let resolvedSchedule: String
            if triggerType == .fileWatch {
                resolvedSchedule = "watch"
            } else {
                resolvedSchedule = try self.resolvedSchedule()
            }
            let normalizedShell = TaskEditorParser.normalizedText(shellPath) ?? "/bin/zsh"

            switch mode {
            case .create:
                try dbManager.addTaskViaCLI(
                    name: trimmedName,
                    schedule: resolvedSchedule,
                    command: resolvedExecution.displayCommand,
                    rawCommand: resolvedExecution.rawCommand,
                    workingDirectory: resolvedExecution.workingDirectory,
                    environment: filteredEnvironment,
                    shell: normalizedShell,
                    triggerType: triggerType.storageValue,
                    watchPath: triggerType == .fileWatch ? watchPath : nil,
                    timeoutSeconds: timeoutSeconds,
                    maxRetries: maxRetries,
                    retryDelaySeconds: retryDelaySeconds,
                    requiresAcPower: requiresAcPower,
                    preventSleep: preventSleep,
                    onSuccessTaskId: onSuccessTaskId.isEmpty ? nil : onSuccessTaskId,
                    onFailureTaskId: onFailureTaskId.isEmpty ? nil : onFailureTaskId
                )
            case .edit(let task):
                try dbManager.updateTaskViaCLI(
                    existingName: task.name,
                    name: trimmedName,
                    schedule: resolvedSchedule,
                    command: resolvedExecution.displayCommand,
                    rawCommand: resolvedExecution.rawCommand,
                    workingDirectory: resolvedExecution.workingDirectory,
                    environment: filteredEnvironment,
                    shell: normalizedShell,
                    triggerType: triggerType.storageValue,
                    watchPath: triggerType == .fileWatch ? watchPath : nil,
                    timeoutSeconds: timeoutSeconds,
                    maxRetries: maxRetries,
                    retryDelaySeconds: retryDelaySeconds,
                    requiresAcPower: requiresAcPower,
                    preventSleep: preventSleep,
                    onSuccessTaskId: onSuccessTaskId.isEmpty ? nil : onSuccessTaskId,
                    onFailureTaskId: onFailureTaskId.isEmpty ? nil : onFailureTaskId
                )
            }

            isPresented = false
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

private struct ValidationError: LocalizedError {
    let message: String

    init(_ message: String) {
        self.message = message
    }

    var errorDescription: String? {
        message
    }
}
