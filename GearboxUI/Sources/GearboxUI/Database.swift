import Foundation
import SQLite3
import Darwin

struct Task: Identifiable, Codable {
    let id: String
    let name: String
    let command: String
    let schedule: String
    let scheduleDesc: String
    var isPaused: Bool
    
    enum CodingKeys: String, CodingKey {
        case id, name, command, schedule
        case scheduleDesc = "schedule_desc"
        case isPaused = "is_paused"
    }
    
    init(id: String, name: String, command: String, schedule: String, scheduleDesc: String, isPaused: Bool) {
        self.id = id
        self.name = name
        self.command = command
        self.schedule = schedule
        self.scheduleDesc = scheduleDesc
        self.isPaused = isPaused
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        command = try container.decode(String.self, forKey: .command)
        schedule = try container.decode(String.self, forKey: .schedule)
        scheduleDesc = try container.decode(String.self, forKey: .scheduleDesc)
        
        // Handle SQLite 0/1 as Bool
        if let boolVal = try? container.decode(Bool.self, forKey: .isPaused) {
            isPaused = boolVal
        } else if let intVal = try? container.decode(Int.self, forKey: .isPaused) {
            isPaused = intVal != 0
        } else {
            isPaused = false
        }
    }
}

struct Run: Identifiable, Codable {
    let id: String
    let taskId: String
    let status: String
    let startedAt: String
    let endedAt: String
    let exitCode: Int
    let stdout: String
    let stderr: String
    
    enum CodingKeys: String, CodingKey {
        case id, status, stdout, stderr
        case taskId = "task_id"
        case startedAt = "started_at"
        case endedAt = "ended_at"
        case exitCode = "exit_code"
    }
}

class DatabaseManager: ObservableObject {
    static let shared = DatabaseManager()
    
    @Published var tasks: [Task] = []
    @Published var recentRuns: [Run] = []
    @Published var activeTaskIds: Set<String> = []
    @Published var hasFailures: Bool = false
    
    private var db: OpaquePointer?
    private let dbPath = NSString(string: "~/.gearbox/gearbox.db").expandingTildeInPath
    private var openedDatabaseIdentifier: AnyHashable?
    
    private init() {
        openDB()
        fetchData()
    }
    
    func openDB() {
        closeDB()

        guard FileManager.default.fileExists(atPath: dbPath) else {
            db = nil
            openedDatabaseIdentifier = nil
            return
        }

        if sqlite3_open(dbPath, &db) != SQLITE_OK {
            print("Error opening database at \(dbPath)")
            closeDB()
            return
        }

        openedDatabaseIdentifier = databaseIdentifier()
    }

    private func closeDB() {
        if let db {
            sqlite3_close(db)
            self.db = nil
        }
    }

    private func databaseIdentifier() -> AnyHashable? {
        let url = URL(fileURLWithPath: dbPath)
        guard let identifier = try? url.resourceValues(forKeys: [.fileResourceIdentifierKey]).fileResourceIdentifier else {
            return nil
        }
        return identifier as? AnyHashable
    }

    private func ensureDBConnection() {
        let fileExists = FileManager.default.fileExists(atPath: dbPath)
        let currentIdentifier = fileExists ? databaseIdentifier() : nil

        if !fileExists {
            if db != nil || openedDatabaseIdentifier != nil {
                closeDB()
                openedDatabaseIdentifier = nil
            }
            return
        }

        if db == nil || currentIdentifier != openedDatabaseIdentifier {
            openDB()
        }
    }

    private func bundledResourcePath(_ relativePath: String) -> String? {
        guard let resourceURL = Bundle.main.resourceURL else {
            return nil
        }

        let bundledPath = resourceURL.appendingPathComponent(relativePath).path
        return FileManager.default.fileExists(atPath: bundledPath) ? bundledPath : nil
    }
    
    private func getPythonPath() -> String {
        if let bundledPython = bundledResourcePath("venv/bin/python3") {
            return bundledPython
        }

        let homeDir = FileManager.default.homeDirectoryForCurrentUser
        let defaultPath = homeDir.appendingPathComponent("Documents/Gearbox/venv/bin/python").path
        if FileManager.default.fileExists(atPath: defaultPath) {
            return defaultPath
        }

        let bundlePath = Bundle.main.bundleURL
        let projectRoot = bundlePath.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let localVenv = projectRoot.appendingPathComponent("venv/bin/python").path
        if FileManager.default.fileExists(atPath: localVenv) {
            return localVenv
        }

        return "python3"
    }
    
    private func getScriptPath(_ name: String) -> String {
        if let bundledScript = bundledResourcePath("python/\(name)") {
            return bundledScript
        }

        let bundlePath = Bundle.main.bundleURL
        let projectRoot = bundlePath.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let localScript = projectRoot.appendingPathComponent(name).path
        if FileManager.default.fileExists(atPath: localScript) {
            return localScript
        }

        let homeDir = FileManager.default.homeDirectoryForCurrentUser
        return homeDir.appendingPathComponent("Documents/Gearbox/\(name)").path
    }

    func syncSchedules() {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: getPythonPath())
        process.arguments = [getScriptPath("cli.py"), "sync-schedules"]
        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            print("Failed to sync schedules: \(error)")
        }
    }
    
    private func formatDisplayDate(_ isoString: String) -> String {
        if isoString.isEmpty { return "" }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
        if let date = formatter.date(from: isoString) {
            formatter.dateStyle = .medium
            formatter.timeStyle = .short
            return formatter.string(from: date)
        }
        
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        if let date = formatter.date(from: isoString) {
            formatter.dateStyle = .medium
            formatter.timeStyle = .short
            return formatter.string(from: date)
        }
        
        return isoString
    }
    
    func fetchData() {
        ensureDBConnection()

        guard db != nil else {
            DispatchQueue.main.async {
                self.tasks = []
                self.recentRuns = []
                self.activeTaskIds = []
                self.hasFailures = false
            }
            return
        }

        var newTasks: [Task] = []
        let taskQuery = "SELECT id, name, command, schedule, is_paused, schedule_desc FROM tasks ORDER BY name ASC;"
        var stmt: OpaquePointer?
        if sqlite3_prepare_v2(db, taskQuery, -1, &stmt, nil) == SQLITE_OK {
            while sqlite3_step(stmt) == SQLITE_ROW {
                let id = String(cString: sqlite3_column_text(stmt, 0))
                let name = String(cString: sqlite3_column_text(stmt, 1))
                let cmd = String(cString: sqlite3_column_text(stmt, 2))
                let sched = String(cString: sqlite3_column_text(stmt, 3))
                let isPaused = sqlite3_column_int(stmt, 4) != 0
                
                let descPtr = sqlite3_column_text(stmt, 5)
                let desc = descPtr != nil ? String(cString: descPtr!) : sched
                
                newTasks.append(Task(id: id, name: name, command: cmd, schedule: sched, scheduleDesc: desc, isPaused: isPaused))
            }
        }
        sqlite3_finalize(stmt)
        
        var activeIds = Set<String>()
        let activeQuery = "SELECT DISTINCT task_id FROM runs WHERE status = 'running';"
        if sqlite3_prepare_v2(db, activeQuery, -1, &stmt, nil) == SQLITE_OK {
            while sqlite3_step(stmt) == SQLITE_ROW {
                let rId = String(cString: sqlite3_column_text(stmt, 0))
                activeIds.insert(rId)
            }
        }
        sqlite3_finalize(stmt)
        
        var newRuns: [Run] = []
        let runQuery = "SELECT id, task_id, status, started_at, ended_at, exit_code, stdout, stderr FROM runs ORDER BY started_at DESC LIMIT 5;"
        if sqlite3_prepare_v2(db, runQuery, -1, &stmt, nil) == SQLITE_OK {
            while sqlite3_step(stmt) == SQLITE_ROW {
                let id = String(cString: sqlite3_column_text(stmt, 0))
                let taskId = String(cString: sqlite3_column_text(stmt, 1))
                let status = String(cString: sqlite3_column_text(stmt, 2))
                let startedAtIso = String(cString: sqlite3_column_text(stmt, 3))
                let startedAt = formatDisplayDate(startedAtIso)
                
                let endedPtr = sqlite3_column_text(stmt, 4)
                let endedAtIso = endedPtr != nil ? String(cString: endedPtr!) : ""
                let endedAt = formatDisplayDate(endedAtIso)
                
                let exitCode = Int(sqlite3_column_int(stmt, 5))
                
                let stdoutPtr = sqlite3_column_text(stmt, 6)
                let stdout = stdoutPtr != nil ? String(cString: stdoutPtr!) : ""
                
                let stderrPtr = sqlite3_column_text(stmt, 7)
                let stderr = stderrPtr != nil ? String(cString: stderrPtr!) : ""
                
                newRuns.append(Run(id: id, taskId: taskId, status: status, startedAt: startedAt, endedAt: endedAt, exitCode: exitCode, stdout: stdout, stderr: stderr))
            }
        }
        sqlite3_finalize(stmt)
        
        DispatchQueue.main.async {
            self.tasks = newTasks
            self.recentRuns = newRuns
            self.activeTaskIds = activeIds
            self.hasFailures = newRuns.prefix(3).contains { $0.status == "failed" }
        }
    }
    
    func togglePause(task: Task) {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: getPythonPath())
        process.arguments = [getScriptPath("cli.py"), task.isPaused ? "resume" : "pause", task.name]
        try? process.run()
        process.waitUntilExit()
        DispatchQueue.main.async { self.fetchData() }
    }
    
    func addTaskViaCLI(name: String, schedule: String, command: String) throws {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: getPythonPath())
        process.arguments = [getScriptPath("cli.py"), "add", name, schedule, command]
        try process.run()
        process.waitUntilExit()
        if process.terminationStatus != 0 {
            throw NSError(domain: "Gearbox", code: 1, userInfo: [NSLocalizedDescriptionKey: "Failed to add task."])
        }
        DispatchQueue.main.async { self.fetchData() }
    }
    
    func fetchLiveLog(runId: String) -> String? {
        let homeDir = FileManager.default.homeDirectoryForCurrentUser
        let logPath = homeDir.appendingPathComponent(".gearbox/logs/\(runId).log").path
        
        if FileManager.default.fileExists(atPath: logPath) {
            return try? String(contentsOfFile: logPath, encoding: .utf8)
        }
        return nil
    }

    func removeTaskViaCLI(name: String) {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: getPythonPath())
        process.arguments = [getScriptPath("cli.py"), "rm", name]
        try? process.run()
        process.waitUntilExit()
        DispatchQueue.main.async { self.fetchData() }
    }

    func stopTaskViaCLI(name: String) {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: getPythonPath())
        process.arguments = [getScriptPath("cli.py"), "stop", name]
        try? process.run()
        process.waitUntilExit()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { self.fetchData() }
    }

    func runTaskManually(name: String) {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: getPythonPath())
        process.arguments = [getScriptPath("cli.py"), "run", name, "--bg"]
        try? process.run()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { self.fetchData() }
    }

    func fetchRuns(for taskId: String) -> [Run] {
        ensureDBConnection()
        guard db != nil else { return [] }

        var results: [Run] = []
        let runQuery = "SELECT id, task_id, status, started_at, ended_at, exit_code, stdout, stderr FROM runs WHERE task_id = ? ORDER BY started_at DESC LIMIT 50;"
        var stmt: OpaquePointer?
        if sqlite3_prepare_v2(db, runQuery, -1, &stmt, nil) == SQLITE_OK {
            taskId.withCString { cString in
                sqlite3_bind_text(stmt, 1, cString, -1, nil)
                while sqlite3_step(stmt) == SQLITE_ROW {
                    let id = String(cString: sqlite3_column_text(stmt, 0))
                    let tId = String(cString: sqlite3_column_text(stmt, 1))
                    let status = String(cString: sqlite3_column_text(stmt, 2))
                    
                    let startedAtIso = String(cString: sqlite3_column_text(stmt, 3))
                    let startedAt = formatDisplayDate(startedAtIso)
                    
                    let endedPtr = sqlite3_column_text(stmt, 4)
                    let endedAtIso = endedPtr != nil ? String(cString: endedPtr!) : ""
                    let endedAt = formatDisplayDate(endedAtIso)
                    
                    let exitCode = Int(sqlite3_column_int(stmt, 5))
                    
                    let stdoutPtr = sqlite3_column_text(stmt, 6)
                    let stdout = stdoutPtr != nil ? String(cString: stdoutPtr!) : ""
                    
                    let stderrPtr = sqlite3_column_text(stmt, 7)
                    let stderr = stderrPtr != nil ? String(cString: stderrPtr!) : ""
                    
                    results.append(Run(id: id, taskId: tId, status: status, startedAt: startedAt, endedAt: endedAt, exitCode: exitCode, stdout: stdout, stderr: stderr))
                }
            }
        }
        sqlite3_finalize(stmt)
        return results
    }
    
    deinit {
        closeDB()
    }
}
