class Gearbox < Formula
  include Language::Python::Virtualenv

  desc "SwiftUI-based macOS menu bar task manager with Python backend"
  homepage "https://github.com/hgayan7/gearbox"
  # Official Release URL
  url "https://github.com/hgayan7/gearbox/archive/refs/tags/v1.0.0.tar.gz"
  version "1.0.0"
  sha256 "fe8baf2553cd7673f6d00e228edb8e1145a898f4892be45ba5d63b4a729cff59"
  license "Apache-2.0"

  depends_on "python@3.11"
  depends_on :xcode => ["14.0", :build]

  resource "click" do
    url "https://pypi.org/packages/source/c/click/click-8.1.7.tar.gz"
    sha256 "ca9853ad459e787e2192211578cc907e7594e294c7ccc834310722b41b9ca6de"
  end

  resource "six" do
    url "https://pypi.org/packages/source/s/six/six-1.17.0.tar.gz"
    sha256 "ff70335d468e7eb6ec65b95b99d3a2836546063f63acc5171de367e834932a81"
  end

  resource "pytz" do
    url "https://pypi.org/packages/source/p/pytz/pytz-2024.1.tar.gz"
    sha256 "2a29735ea9c18baf14b448846bde5a48030ed267578472d8955cd0e7443a9812"
  end

  resource "tzlocal" do
    url "https://pypi.org/packages/source/t/tzlocal/tzlocal-5.2.tar.gz"
    sha256 "8d399205578f1a9342816409cc1e46a93ebd5755e39ea2d85334bea911bf0e6e"
  end

  resource "apscheduler" do
    url "https://pypi.org/packages/source/A/APScheduler/APScheduler-3.10.4.tar.gz"
    sha256 "e6df071b27d9be898e486bc7940a7be50b4af2e9da7c08f0744a96d4bd4cef4a"
  end

  resource "cron-descriptor" do
    url "https://pypi.org/packages/source/c/cron-descriptor/cron_descriptor-1.4.3.tar.gz"
    sha256 "7b1a00d7d25d6ae6896c0da4457e790b98cba778398a3d48e341e5e0d33f0488"
  end

  def install
    venv = virtualenv_create(libexec, "python3.11")
    venv.pip_install resources
    
    # Install Python source files
    libexec.install "cli.py", "daemon.py", "core"
    
    # Create wrapper script
    (bin/"gearbox").write <<~EOS
      #!/bin/bash
      export PATH="#{bin}:$PATH"
      exec "#{libexec}/bin/python3" "#{libexec}/cli.py" "$@"
    EOS

    # Build Swift UI
    cd "GearboxUI" do
      system "swift", "build", "-c", "release", "--disable-sandbox"
      
      app_path = libexec/"Gearbox.app"
      (app_path/"Contents/MacOS").mkpath
      (app_path/"Contents/Resources").mkpath
      
      cp ".build/release/GearboxUI", app_path/"Contents/MacOS/"
      
      (app_path/"Contents/Info.plist").write <<~EOS
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>CFBundleExecutable</key>
            <string>GearboxUI</string>
            <key>CFBundleIdentifier</key>
            <string>com.gearbox.ui</string>
            <key>CFBundleName</key>
            <string>Gearbox</string>
            <key>CFBundleVersion</key>
            <string>#{version}</string>
            <key>LSUIElement</key>
            <true/>
        </dict>
        </plist>
      EOS
    end
  end

  def post_install
    system "codesign", "--force", "--deep", "-s", "-", libexec/"Gearbox.app"
  end

  service do
    run [libexec/"bin/python3", libexec/"daemon.py"]
    keep_alive true
    log_path var/"log/gearbox-daemon.log"
    error_log_path var/"log/gearbox-daemon-error.log"
  end

  def caveats
    <<~EOS
      To start the native macOS menu bar UI, run:
        open #{opt_libexec}/Gearbox.app

      To start the background daemon as a service:
        brew services start gearbox
    EOS
  end

  test do
    system "#{bin}/gearbox", "--help"
  end
end
