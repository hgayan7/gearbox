cask "gearbox" do
  version "1.0.3"
  sha256 "93ce2fce49bdb3eebfb5c52893c723f6462cb7cd8f750a283f64a5800f947c9f"

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
