cask "gearbox" do
  version "1.0.6"
  sha256 "bac19eb81dac0d2adfdbdb57ee2471aca5fd6d98231180aa24acb26b9a717336"

  url "https://github.com/hgayan7/gearbox/releases/download/v#{version}/gearbox-#{version}.zip"
  name "Gearbox"
  desc "SwiftUI-based macOS menu bar task manager with Python backend"
  homepage "https://github.com/hgayan7/gearbox"
  depends_on formula: "python@3.11"

  app "Gearbox.app"
  binary "Gearbox.app/Contents/MacOS/gearbox"

  zap trash: [
    "~/.gearbox",
    "~/Library/Application Support/Gearbox",
    "~/Library/Caches/com.gearbox.ui",
    "~/Library/Preferences/com.gearbox.ui.plist",
    "~/Library/LaunchAgents/com.gearbox.ui.plist",
    "~/Library/LaunchAgents/com.gearbox.daemon.plist",
    "~/Library/LaunchAgents/com.gearbox.task.*.plist",
  ]
end
