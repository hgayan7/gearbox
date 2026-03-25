import Foundation
import SQLite3

struct Task: Identifiable {
    let id: String
    let name: String
    let command: String
    let schedule: String
    let scheduleDesc: String
    var isPaused: Bool
}

struct Run: Identifiable {
    let id: String
    let taskId: String
    let status: String
    let startedAt: String
    let endedAt: String
    let exitCode: Int
    let stdout: String
    let stderr: String
}

class DatabaseManager: ObservableObject {
    static let shared = DatabaseManager()
    
    @Published var tasks: [Task] = []
    @Published var recentRuns: [Run] = []
    @Published var activeTaskIds: Set<String> = []
    @Published var hasFailures: Bool = false
    
    private var db: OpaquePointer?
    var daemonProcess: Process?
    
    private init() {
        openDB()
        fetchData()
    }
    
    func openDB() {
        let expandPath = NSString(string: "~/.gearbox/gearbox.db").expandingTildeInPath
        if sqlite3_open(expandPath, &db) != SQLITE_OK {
            print("Error opening database")
        }
    }
    
    private func getPythonPath() -> String {
        // Try to find the project root from the executable path (if running from build folder)
        // OR default to a standard location if we add one later.
        // For now, let's assume it's in the same parent dir as the .app bundle 
        // which is standard for this project's layout.
        
        // This is a bit of a heuristic for the local dev/install setup
        let homeDir = FileManager.default.homeDirectoryForCurrentUser
        let defaultPath = homeDir.appendingPathComponent("Documents/Gearbox/venv/bin/python").path
        
        if FileManager.default.fileExists(atPath: defaultPath) {
            return defaultPath
        }
        
        // Fallback to expecting it in the same directory as the app's parent
        let bundlePath = Bundle.main.bundleURL
        let projectRoot = bundlePath.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let localVenv = projectRoot.appendingPathComponent("venv/bin/python").path
        
        if FileManager.default.fileExists(atPath: localVenv) {
            return localVenv
        }
        
        return "python3" // Last resort: system python
    }
    
    private func getScriptPath(_ name: String) -> String {
        let bundlePath = Bundle.main.bundleURL
        let projectRoot = bundlePath.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let localScript = projectRoot.appendingPathComponent(name).path
        
        if FileManager.default.fileExists(atPath: localScript) {
            return localScript
        }
        
        // Fallback to home dir
        let homeDir = FileManager.default.homeDirectoryForCurrentUser
        return homeDir.appendingPathComponent("Documents/Gearbox/\(name)").path
    }
    
    func startDaemon() {
        if daemonProcess != nil { return }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: getPythonPath())
        process.arguments = [getScriptPath("daemon.py")]
        do {
            try process.run()
            self.daemonProcess = process
            print("Daemon started as child process.")
        } catch {
            print("Failed to start daemon: \(error)")
        }
    }
    
    func stopDaemon() {
        daemonProcess?.terminate()
        daemonProcess = nil
        print("Daemon stopped.")
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
        let updateQuery = "UPDATE tasks SET is_paused = ? WHERE id = ?;"
        var stmt: OpaquePointer?
        if sqlite3_prepare_v2(db, updateQuery, -1, &stmt, nil) == SQLITE_OK {
            sqlite3_bind_int(stmt, 1, !task.isPaused ? 1 : 0)
            let idString = task.id as NSString
            sqlite3_bind_text(stmt, 2, idString.utf8String, -1, nil)
            
            if sqlite3_step(stmt) == SQLITE_DONE {
                DispatchQueue.main.async {
                    self.fetchData()
                }
            }
        }
        sqlite3_finalize(stmt)
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
        var results: [Run] = []
        let runQuery = "SELECT id, task_id, status, started_at, ended_at, exit_code, stdout, stderr FROM runs WHERE task_id = ? ORDER BY started_at DESC LIMIT 50;"
        var stmt: OpaquePointer?
        if sqlite3_prepare_v2(db, runQuery, -1, &stmt, nil) == SQLITE_OK {
            let idString = taskId as NSString
            sqlite3_bind_text(stmt, 1, idString.utf8String, -1, nil)
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
        sqlite3_finalize(stmt)
        return results
    }
    
    deinit {
        sqlite3_close(db)
    }
}
