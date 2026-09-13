import Foundation
import Network

public class WebhookServer: ObservableObject {
    public static let shared = WebhookServer()

    @Published public private(set) var isRunning: Bool = false
    @Published public private(set) var port: UInt16 = 43272
    @Published public var lastTriggeredTask: String? = nil

    private var listener: NWListener?
    private let queue = DispatchQueue(label: "com.gearbox.webhook", qos: .utility)

    private init() {}

    public func start(portNumber: UInt16 = 43272) {
        guard !isRunning else { return }
        self.port = portNumber

        do {
            let params = NWParameters.tcp
            params.allowLocalEndpointReuse = true
            let listener = try NWListener(using: params, on: NWEndpoint.Port(integerLiteral: portNumber))

            listener.stateUpdateHandler = { [weak self] state in
                DispatchQueue.main.async {
                    switch state {
                    case .ready:
                        self?.isRunning = true
                    case .failed(let error):
                        print("[Gearbox Webhook] Server failed: \(error)")
                        self?.isRunning = false
                    case .cancelled:
                        self?.isRunning = false
                    default:
                        break
                    }
                }
            }

            listener.newConnectionHandler = { [weak self] connection in
                self?.handleConnection(connection)
            }

            listener.start(queue: self.queue)
            self.listener = listener
        } catch {
            print("[Gearbox Webhook] Failed to create NWListener on port \(portNumber): \(error)")
        }
    }

    public func stop() {
        listener?.cancel()
        listener = nil
        DispatchQueue.main.async {
            self.isRunning = false
        }
    }

    private func handleConnection(_ connection: NWConnection) {
        connection.start(queue: self.queue)
        readRequest(connection: connection)
    }

    private func readRequest(connection: NWConnection) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] content, _, isComplete, error in
            guard let self = self else { return }
            if let data = content, let requestString = String(data: data, encoding: .utf8) {
                let responseData = self.processHTTPRequest(requestString)
                connection.send(content: responseData, completion: .contentProcessed({ _ in
                    connection.cancel()
                }))
            } else if isComplete || error != nil {
                connection.cancel()
            }
        }
    }

    private func processHTTPRequest(_ raw: String) -> Data {
        let lines = raw.components(separatedBy: "\r\n").flatMap { $0.components(separatedBy: "\n") }
        guard let requestLine = lines.first(where: { !$0.isEmpty }) else {
            return makeHTTPResponse(status: "400 Bad Request", body: ["error": "Empty request"])
        }

        let parts = requestLine.components(separatedBy: " ")
        guard parts.count >= 2 else {
            return makeHTTPResponse(status: "400 Bad Request", body: ["error": "Malformed request"])
        }

        let method = parts[0].uppercased()
        let path = parts[1]

        // Routing
        if method == "GET" && (path == "/status" || path == "/") {
            let tasks = DatabaseManager.shared.tasks
            let runs = DatabaseManager.shared.recentRuns
            let activeRuns = runs.filter { $0.status == "running" }.count
            return makeHTTPResponse(status: "200 OK", body: [
                "status": "ok",
                "service": "Gearbox Automation Engine",
                "version": "1.2.0",
                "tasks_count": tasks.count,
                "active_runs_count": activeRuns,
            ])
        }

        if method == "GET" && path == "/tasks" {
            let taskDicts = DatabaseManager.shared.tasks.map { t in
                [
                    "id": t.id,
                    "name": t.name,
                    "schedule": t.schedule,
                    "trigger_type": t.triggerType,
                    "is_paused": t.isPaused
                ] as [String : Any]
            }
            return makeHTTPResponse(status: "200 OK", body: ["tasks": taskDicts])
        }

        if (method == "POST" || method == "GET") && path.hasPrefix("/run/") {
            let encodedName = String(path.dropFirst("/run/".count))
            let taskName = encodedName.removingPercentEncoding ?? encodedName
            if !taskName.isEmpty {
                DispatchQueue.main.async {
                    DatabaseManager.shared.runTaskManually(name: taskName)
                    self.lastTriggeredTask = taskName
                }
                return makeHTTPResponse(status: "200 OK", body: [
                    "status": "triggered",
                    "task": taskName
                ])
            }
        }

        if method == "POST" && path.hasPrefix("/pause/") {
            let encodedName = String(path.dropFirst("/pause/".count))
            let taskName = encodedName.removingPercentEncoding ?? encodedName
            if let task = DatabaseManager.shared.tasks.first(where: { $0.name == taskName }) {
                DispatchQueue.main.async {
                    if !task.isPaused {
                        DatabaseManager.shared.togglePause(task: task)
                    }
                }
                return makeHTTPResponse(status: "200 OK", body: [
                    "status": "paused",
                    "task": taskName
                ])
            }
        }

        if method == "POST" && path.hasPrefix("/resume/") {
            let encodedName = String(path.dropFirst("/resume/".count))
            let taskName = encodedName.removingPercentEncoding ?? encodedName
            if let task = DatabaseManager.shared.tasks.first(where: { $0.name == taskName }) {
                DispatchQueue.main.async {
                    if task.isPaused {
                        DatabaseManager.shared.togglePause(task: task)
                    }
                }
                return makeHTTPResponse(status: "200 OK", body: [
                    "status": "resumed",
                    "task": taskName
                ])
            }
        }

        return makeHTTPResponse(status: "404 Not Found", body: [
            "error": "Route not found",
            "path": path,
            "method": method
        ])
    }

    private func makeHTTPResponse(status: String, body: Any) -> Data {
        let jsonData: Data
        do {
            jsonData = try JSONSerialization.data(withJSONObject: body, options: [.prettyPrinted])
        } catch {
            jsonData = "{\"error\": \"JSON serialization error\"}".data(using: .utf8)!
        }

        var header = "HTTP/1.1 \(status)\r\n"
        header += "Content-Type: application/json; charset=utf-8\r\n"
        header += "Access-Control-Allow-Origin: *\r\n"
        header += "Content-Length: \(jsonData.count)\r\n"
        header += "Connection: close\r\n\r\n"

        var response = header.data(using: .utf8) ?? Data()
        response.append(jsonData)
        return response
    }
}
