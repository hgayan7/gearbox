cask "gearbox" do
  version "1.0.1"
  sha256 "540743643d549e1b177cff1b4e145d632c86fc29f19951849128b4ca77ad1acf"

  url "https://github.com/hgayan7/gearbox/releases/download/v#{version}/gearbox-#{version}.zip"
  name "Gearbox"
  desc "SwiftUI-based macOS menu bar task manager with Python backend"
  homepage "https://github.com/hgayan7/gearbox"

  app "Gearbox.app"
  binary "Gearbox.app/Contents/MacOS/gearbox"

  zap trash: [
    "~/.gearbox",
    "~/Library/Application Support/Gearbox",
    "~/Library/Caches/com.gearbox.ui",
    "~/Library/Preferences/com.gearbox.ui.plist",
    "~/Library/LaunchAgents/com.gearbox.ui.plist",
    "~/Library/LaunchAgents/com.gearbox.daemon.plist",
  ]
end
