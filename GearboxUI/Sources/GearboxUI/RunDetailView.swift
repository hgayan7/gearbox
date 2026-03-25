import SwiftUI

struct RunDetailView: View {
    let run: Run
    let command: String
    @ObservedObject var dbManager: DatabaseManager
    
    @State private var liveLogContent: String = ""
    let timer = Timer.publish(every: 1.5, on: .main, in: .common).autoconnect()
    
    private var logContent: String {
        if run.status == "running" {
            return liveLogContent.isEmpty ? "(Waiting for output...)" : liveLogContent
        }
        return run.stdout.isEmpty ? "(No output)" : run.stdout
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Image(systemName: "terminal")
                            .font(.system(size: 11))
                        Text(run.status == "running" ? "Live logs" : "Execution logs")
                            .font(.system(size: 13, weight: .semibold))
                    }
                    if !command.isEmpty {
                        Text(command)
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundColor(.secondary.opacity(0.7))
                            .lineLimit(1)
                            .truncationMode(.middle)
                    }
                }
                Spacer()
                Text(run.status == "running" ? "Started \(run.startedAt.split(separator: " ").last ?? "")" : "Ended at \(run.endedAt.split(separator: " ").last ?? "")")
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 12)
            .background(VisualEffectView(material: .headerView, blendingMode: .withinWindow))
            
            Divider()
            
            VStack(alignment: .leading, spacing: 0) {
                Text(run.status == "running" ? "REAL-TIME OUTPUT" : "OUTPUT")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundColor(run.status == "running" ? .blue : .secondary)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 6)
                
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 0) {
                            Text(logContent)
                                .font(.system(size: 11, design: .monospaced))
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(16)
                            
                            Color.clear
                                .frame(height: 1)
                                .id("bottom")
                        }
                    }
                    .onChange(of: logContent) { _ in
                        withAnimation {
                            proxy.scrollTo("bottom", anchor: .bottom)
                        }
                    }
                }
            }
        }
        .background(Color(nsColor: .textBackgroundColor))
        .onAppear { updateLiveLog() }
        .onReceive(timer) { _ in updateLiveLog() }
    }
    
    private func updateLiveLog() {
        guard run.status == "running" else { return }
        if let live = dbManager.fetchLiveLog(runId: run.id) {
            self.liveLogContent = live
        }
    }
}
