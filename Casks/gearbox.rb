cask "gearbox" do
  version "1.2.0"
  sha256 "e119b64e714ddaec293d352c023b49cad7ed1a1380ff1b54f3dbaf6f286c66fe"

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
