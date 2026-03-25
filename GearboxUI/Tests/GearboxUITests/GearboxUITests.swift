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
    }
}
