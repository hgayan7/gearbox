import SwiftUI

struct RunDetailView: View {
    let run: Run
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                HStack(spacing: 6) {
                    Image(systemName: "terminal")
                        .font(.system(size: 11))
                    Text("Execution logs")
                        .font(.system(size: 13, weight: .semibold))
                }
                Spacer()
                Text("Ended at \(run.endedAt.split(separator: " ").last ?? "")")
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 12)
            .background(VisualEffectView(material: .headerView, blendingMode: .withinWindow))
            
            Divider()
            
            GeometryReader { geo in
                HStack(spacing: 1) {
                    // Stdout
                    VStack(alignment: .leading, spacing: 0) {
                        Text("OUTPUT")
                            .font(.system(size: 9, weight: .bold))
                            .foregroundColor(.secondary)
                            .padding(.horizontal, 16)
                            .padding(.vertical, 6)
                        
                        ScrollView {
                            Text(run.stdout.isEmpty ? "(No output)" : run.stdout)
                                .font(.system(size: 11, design: .monospaced))
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(16)
                        }
                    }
                    .frame(width: geo.size.width / 2)
                    
                    Rectangle()
                        .fill(Color.primary.opacity(0.1))
                        .frame(width: 1)
                    
                    // Stderr
                    VStack(alignment: .leading, spacing: 0) {
                        Text("ERRORS")
                            .font(.system(size: 9, weight: .bold))
                            .foregroundColor(.red.opacity(0.7))
                            .padding(.horizontal, 16)
                            .padding(.vertical, 6)
                        
                        ScrollView {
                            Text(run.stderr.isEmpty ? "(No errors)" : run.stderr)
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundColor(.red.opacity(0.8))
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(16)
                        }
                    }
                    .frame(width: geo.size.width / 2)
                }
            }
        }
        .background(Color(nsColor: .textBackgroundColor))
    }
}
