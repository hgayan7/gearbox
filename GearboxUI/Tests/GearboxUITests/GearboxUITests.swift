import XCTest
@testable import GearboxUI

final class GearboxUITests: XCTestCase {
    
    func testTaskDecoding() throws {
        let json = """
        {
            "id": "123",
            "name": "Test Task",
            "command": "echo hello",
            "schedule": "* * * * *",
            "schedule_desc": "Every minute",
            "is_paused": 0
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        let task = try decoder.decode(Task.self, from: json)
        
        XCTAssertEqual(task.id, "123")
        XCTAssertEqual(task.name, "Test Task")
        XCTAssertEqual(task.isPaused, false)
    }
    
    func testRunDecoding() throws {
        let json = """
        {
            "id": "run-456",
            "task_id": "123",
            "status": "success",
            "started_at": "2024-03-25 10:00:00",
            "ended_at": "2024-03-25 10:00:05",
            "exit_code": 0,
            "stdout": "done",
            "stderr": ""
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        let run = try decoder.decode(Run.self, from: json)
        
        XCTAssertEqual(run.id, "run-456")
        XCTAssertEqual(run.status, "success")
        XCTAssertEqual(run.exitCode, 0)
        XCTAssertEqual(run.stdout, "done")
        XCTAssertEqual(run.retryCount, 0)
        XCTAssertEqual(run.triggerSource, "schedule")
    }

    func testTaskDecodingWithPart1Fields() throws {
        let json = """
        {
            "id": "789",
            "name": "Watch Downloads",
            "command": "python clean.py",
            "schedule": "watch",
            "schedule_desc": "Folder Watcher",
            "is_paused": 0,
            "trigger_type": "file_watch",
            "watch_path": "/Users/test/Downloads",
            "timeout_seconds": 120,
            "max_retries": 3,
            "retry_delay_seconds": 15,
            "requires_ac_power": 1,
            "prevent_sleep": 1,
            "on_success_task_id": "succ-1",
            "on_failure_task_id": "fail-1"
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        let task = try decoder.decode(Task.self, from: json)

        XCTAssertEqual(task.id, "789")
        XCTAssertEqual(task.name, "Watch Downloads")
        XCTAssertEqual(task.triggerType, "file_watch")
        XCTAssertEqual(task.watchPath, "/Users/test/Downloads")
        XCTAssertEqual(task.timeoutSeconds, 120)
        XCTAssertEqual(task.maxRetries, 3)
        XCTAssertEqual(task.retryDelaySeconds, 15)
        XCTAssertEqual(task.requiresAcPower, true)
        XCTAssertEqual(task.preventSleep, true)
        XCTAssertEqual(task.onSuccessTaskId, "succ-1")
        XCTAssertEqual(task.onFailureTaskId, "fail-1")
    }

    func testRunDecodingWithPart1Fields() throws {
        let json = """
        {
            "id": "run-789",
            "task_id": "789",
            "status": "failed",
            "started_at": "2024-03-25 10:00:00",
            "ended_at": "2024-03-25 10:00:05",
            "exit_code": 1,
            "stdout": "",
            "stderr": "error",
            "retry_count": 2,
            "trigger_source": "retry"
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        let run = try decoder.decode(Run.self, from: json)

        XCTAssertEqual(run.id, "run-789")
        XCTAssertEqual(run.status, "failed")
        XCTAssertEqual(run.exitCode, 1)
        XCTAssertEqual(run.retryCount, 2)
        XCTAssertEqual(run.triggerSource, "retry")
    }

    func testTriggerTypeEnum() throws {
        XCTAssertEqual(TaskTriggerType.from(storageValue: "file_watch"), .fileWatch)
        XCTAssertEqual(TaskTriggerType.from(storageValue: "cron"), .cron)
        XCTAssertEqual(TaskTriggerType.from(storageValue: nil), .cron)
        XCTAssertEqual(TaskTriggerType.fileWatch.storageValue, "file_watch")
        XCTAssertEqual(TaskTriggerType.cron.storageValue, "cron")
    }

    func testDatabaseManagerActivityProperties() throws {
        let dbManager = DatabaseManager.shared

        let task1 = Task(
            id: "t-1",
            name: "Task One",
            command: "echo 1",
            schedule: "0 10 * * *",
            scheduleDesc: "At 10:00 AM",
            rawCommand: nil,
            workingDirectory: nil,
            environment: [:],
            shell: nil,
            isPaused: false,
            triggerType: "cron"
        )
        dbManager.tasks = [task1]

        let runRunning = Run(
            id: "r-run",
            taskId: "t-1",
            status: "running",
            startedAt: "2026-09-14 10:00:00",
            endedAt: "",
            exitCode: 0,
            stdout: "",
            stderr: ""
        )
        let runFailed = Run(
            id: "r-fail",
            taskId: "t-1",
            status: "failed",
            startedAt: "2026-09-14 09:00:00",
            endedAt: "2026-09-14 09:00:01",
            exitCode: 1,
            stdout: "",
            stderr: "err"
        )

        dbManager.recentRuns = [runRunning, runFailed]
        XCTAssertTrue(dbManager.hasActiveRun)
        XCTAssertEqual(dbManager.recentFailureCount, 1)
        XCTAssertEqual(dbManager.nextUpcomingTaskSummary, "Task One: At 10:00 AM")
    }

    func testAppIntentsCreation() throws {
        if #available(macOS 13.0, *) {
            let runIntent = RunTaskIntent(taskName: "Sample Task")
            XCTAssertEqual(runIntent.taskName, "Sample Task")

            let pauseIntent = PauseTaskIntent(taskName: "Sample Task")
            XCTAssertEqual(pauseIntent.taskName, "Sample Task")

            let resumeIntent = ResumeTaskIntent(taskName: "Sample Task")
            XCTAssertEqual(resumeIntent.taskName, "Sample Task")
        }
    }
}
