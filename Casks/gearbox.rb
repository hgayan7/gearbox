cask "gearbox" do
  version "1.0.0"
  sha256 "01b5ace64b1a174bf24d1ef5b4f29a03b33e694869dc4c082cab8ebfb1a48919"

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
