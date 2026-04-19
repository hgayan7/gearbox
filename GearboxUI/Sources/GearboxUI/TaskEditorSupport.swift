import Foundation

enum TaskEditorMode {
    case create
    case edit(Task)

    var title: String {
        switch self {
        case .create:
            return "New Automation"
        case .edit:
            return "Edit Automation"
        }
    }

    var subtitle: String {
        switch self {
        case .create:
            return "Schedule a recurring task or script."
        case .edit:
            return "Update execution settings and schedule."
        }
    }

    var primaryButtonTitle: String {
        switch self {
        case .create:
            return "Create Task"
        case .edit:
            return "Save Changes"
        }
    }

    var existingTask: Task? {
        switch self {
        case .create:
            return nil
        case .edit(let task):
            return task
        }
    }
}

enum TaskScheduleMode: String, CaseIterable, Identifiable {
    case preset = "Preset"
    case customCron = "Custom Cron"

    var id: String { rawValue }
}

enum TaskExecutionMode: String, CaseIterable, Identifiable {
    case guided = "Script or Folder"
    case command = "Custom Command"

    var id: String { rawValue }
}

struct ScheduleItem: Identifiable, Equatable {
    let id = UUID()
    var frequency: String = "Daily"
    var time: Date = Date()
    var selectedDay: Int = 1
}

struct EnvironmentVariableRow: Identifiable, Equatable {
    let id = UUID()
    var key: String = ""
    var value: String = ""
}

struct SchedulePreview: Decodable {
    let normalizedSchedule: String
    let description: String
    let timezone: String
    let nextRuns: [String]

    enum CodingKeys: String, CodingKey {
        case description, timezone
        case normalizedSchedule = "normalized_schedule"
        case nextRuns = "next_runs"
    }
}

struct InferredExecutionSettings {
    let rawCommand: String
    let workingDirectory: String?
}

enum TaskEditorParser {
    static func inferExecutionSettings(command: String, rawCommand: String?, workingDirectory: String?) -> InferredExecutionSettings {
        if let rawCommand, !rawCommand.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return InferredExecutionSettings(
                rawCommand: rawCommand,
                workingDirectory: normalizedText(workingDirectory)
            )
        }

        let trimmedCommand = command.trimmingCharacters(in: .whitespacesAndNewlines)
        let pattern = #"^cd '([^']+)' && (.+)$"#
        if
            let regex = try? NSRegularExpression(pattern: pattern),
            let match = regex.firstMatch(in: trimmedCommand, range: NSRange(trimmedCommand.startIndex..., in: trimmedCommand)),
            let directoryRange = Range(match.range(at: 1), in: trimmedCommand),
            let rawCommandRange = Range(match.range(at: 2), in: trimmedCommand)
        {
            return InferredExecutionSettings(
                rawCommand: String(trimmedCommand[rawCommandRange]),
                workingDirectory: String(trimmedCommand[directoryRange])
            )
        }

        return InferredExecutionSettings(rawCommand: trimmedCommand, workingDirectory: normalizedText(workingDirectory))
    }

    static func parsePresetSchedules(schedule: String) -> [ScheduleItem]? {
        let parts = schedule
            .split(separator: "|")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        guard !parts.isEmpty else { return nil }

        let calendar = Calendar.current
        let today = Date()
        var parsed: [ScheduleItem] = []

        for part in parts {
            let tokens = part.split(separator: " ")
            guard tokens.count == 5 else { return nil }

            let minuteToken = String(tokens[0])
            let hourToken = String(tokens[1])
            let dayOfMonth = String(tokens[2])
            let month = String(tokens[3])
            let dayOfWeek = String(tokens[4])

            guard dayOfMonth == "*", month == "*" else { return nil }

            if hourToken == "*", dayOfWeek == "*", let minute = Int(minuteToken) {
                guard minute == 0 else { return nil }
                parsed.append(ScheduleItem(frequency: "Hourly", time: today, selectedDay: 1))
                continue
            }

            guard let hour = Int(hourToken), let minute = Int(minuteToken) else { return nil }
            guard let date = calendar.date(bySettingHour: hour, minute: minute, second: 0, of: today) else {
                return nil
            }

            switch dayOfWeek {
            case "*":
                parsed.append(ScheduleItem(frequency: "Daily", time: date, selectedDay: 1))
            case "1-5":
                parsed.append(ScheduleItem(frequency: "Weekdays (Mon-Fri)", time: date, selectedDay: 1))
            case "0,6":
                parsed.append(ScheduleItem(frequency: "Weekends", time: date, selectedDay: 1))
            default:
                guard let day = Int(dayOfWeek), [0, 1, 2, 3, 4, 5, 6].contains(day) else {
                    return nil
                }
                parsed.append(ScheduleItem(frequency: "Weekly", time: date, selectedDay: day))
            }
        }

        return parsed
    }

    static func normalizedText(_ value: String?) -> String? {
        guard let value else { return nil }
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    static func environmentRows(from environment: [String: String]) -> [EnvironmentVariableRow] {
        environment
            .sorted { $0.key.localizedCaseInsensitiveCompare($1.key) == .orderedAscending }
            .map { EnvironmentVariableRow(key: $0.key, value: $0.value) }
    }
}
