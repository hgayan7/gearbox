import Foundation
import AppIntents

@available(macOS 13.0, *)
public struct RunTaskIntent: AppIntent {
    public static var title: LocalizedStringResource = "Run Gearbox Task"
    public static var description = IntentDescription("Triggers a Gearbox background automation immediately.")

    @Parameter(title: "Task Name")
    public var taskName: String

    public static var parameterSummary: some ParameterSummary {
        Summary("Run \(\.$taskName)")
    }

    public init() {}
    public init(taskName: String) {
        self.taskName = taskName
    }

    @MainActor
    public func perform() async throws -> some IntentResult & ProvidesDialog {
        DatabaseManager.shared.runTaskManually(name: taskName)
        return .result(dialog: "Triggered task \(taskName) in Gearbox.")
    }
}

@available(macOS 13.0, *)
public struct PauseTaskIntent: AppIntent {
    public static var title: LocalizedStringResource = "Pause Gearbox Task"
    public static var description = IntentDescription("Pauses a scheduled task in Gearbox.")

    @Parameter(title: "Task Name")
    public var taskName: String

    public static var parameterSummary: some ParameterSummary {
        Summary("Pause \(\.$taskName)")
    }

    public init() {}
    public init(taskName: String) {
        self.taskName = taskName
    }

    @MainActor
    public func perform() async throws -> some IntentResult & ProvidesDialog {
        if let task = DatabaseManager.shared.tasks.first(where: { $0.name == taskName }) {
            if !task.isPaused {
                DatabaseManager.shared.togglePause(task: task)
            }
            return .result(dialog: "Paused task \(taskName).")
        }
        return .result(dialog: "Task \(taskName) not found.")
    }
}

@available(macOS 13.0, *)
public struct ResumeTaskIntent: AppIntent {
    public static var title: LocalizedStringResource = "Resume Gearbox Task"
    public static var description = IntentDescription("Resumes a paused task in Gearbox.")

    @Parameter(title: "Task Name")
    public var taskName: String

    public static var parameterSummary: some ParameterSummary {
        Summary("Resume \(\.$taskName)")
    }

    public init() {}
    public init(taskName: String) {
        self.taskName = taskName
    }

    @MainActor
    public func perform() async throws -> some IntentResult & ProvidesDialog {
        if let task = DatabaseManager.shared.tasks.first(where: { $0.name == taskName }) {
            if task.isPaused {
                DatabaseManager.shared.togglePause(task: task)
            }
            return .result(dialog: "Resumed task \(taskName).")
        }
        return .result(dialog: "Task \(taskName) not found.")
    }
}

@available(macOS 13.0, *)
public struct GearboxShortcuts: AppShortcutsProvider {
    public static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: RunTaskIntent(),
            phrases: [
                "Run \(\.$taskName) in \(.applicationName)",
                "Execute \(\.$taskName) with \(.applicationName)"
            ],
            shortTitle: "Run Task",
            systemImageName: "play.circle.fill"
        )
    }
}
