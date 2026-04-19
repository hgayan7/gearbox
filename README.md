<p align="center">
  <img src="GearboxUI/Resources/AppIcon.png" width="128" alt="Gearbox App Icon">
</p>

# Gearbox ⚙️

Gearbox is a powerful macOS-native local automation manager. It allows you to schedule and manage background tasks with a clean, modern UI and a flexible CLI.

### Why Gearbox? ⚙️
- **Local First**: Your data stays on your machine in a private SQLite database.
- **Native Feel**: Built with SwiftUI for a premium, lightweight integration with macOS.
- **Python Power**: Leverage the full ecosystem of Python for your automation scripts.
- **Transparent**: Live log streaming means you always know what's happening.



https://github.com/user-attachments/assets/51500ad3-2145-4a78-9967-f05fe34f038b

<img width="288" height="318" alt="Screenshot 2026-03-25 at 10 44 30 PM" src="https://github.com/user-attachments/assets/c3a6fd4d-f502-46d0-a9e6-4df6a39343e3" />


## Features

- **Native macOS Menu Bar UI**: Monitor and control tasks directly from your menu bar with a polished Swift-based app.
- **Shared Create/Edit Task Editor**: Create new automations and update existing ones from the same native editor.
- **Advanced Execution Settings**: Configure raw commands, working directory, shell, and per-task environment variables.
- **Live Log Streaming**: Watch your automations execute in real-time with built-in auto-scrolling. 📡
- **Accurate Status Tracking**: Clear visual indicators for **Success**, **Failed**, **Running**, and **Cancelled** tasks.
- **Flexible Scheduling**: Use preset schedules for common cases or switch to custom cron when you need exact control.
- **Schedule Preview**: See the normalized schedule and the next upcoming run times before saving.
- **Task Isolation**: Each task runs in its own process with full log capture.
- **Background Daemon**: A lightweight Python daemon manages the execution queue.
- **CLI Interface**: Powerful command-line tool for managing tasks.


## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hgayan7/gearbox.git
   cd gearbox
   ```

2. Run the installation script (this will create a virtual environment and install dependencies):
   ```bash
   ./install.sh
   ```

3. (Optional) Add the alias to your shell profile:
   ```bash
   # Add this to your ~/.zshrc or ~/.bash_profile
   alias gearbox='$PWD/venv/bin/python3 $PWD/cli.py'
   ```

### Homebrew (Recommended)

Install Gearbox from the public Homebrew tap:

```bash
brew install --cask hgayan7/gearbox/gearbox
open -a Gearbox
```

After installation, the Gearbox app will be in your `/Applications` folder, and the `gearbox` command will be available in your terminal.

On first launch:

- Homebrew installs the app, but does not automatically start the menu bar app.
- Launch it once with `open -a Gearbox`.
- macOS may block the first launch. If that happens, go to `System Settings > Privacy & Security` and click `Open Anyway`.
- After the first successful launch, the Gearbox icon should appear in the menu bar.

## Usage

### CLI

- **Add a task**: `gearbox add my-task "*/5 * * * *" "echo hello"`
- **Add a task with advanced settings**: `gearbox add sync-job "0 9 * * 1-5" "cd '/tmp/project' && ./run.sh" --raw-command "./run.sh" --working-directory "/tmp/project" --env-json '{"APP_ENV":"prod"}' --shell /bin/zsh`
- **Update a task**: `gearbox update sync-job sync-job "0 10 * * 1-5" "cd '/tmp/project' && ./run.sh" --raw-command "./run.sh" --working-directory "/tmp/project"`
- **List tasks**: `gearbox ls`
- **View logs**: `gearbox logs my-task`
- **View history**: `gearbox history my-task`
- **Pause/Resume**: `gearbox pause my-task` / `gearbox resume my-task`
- **Run now**: `gearbox run my-task`
- **Stop task**: `gearbox stop my-task`
- **Preview a schedule**: `gearbox preview-schedule "0 9 * * 1-5"`

### UI

The native macOS menu bar app appears after you launch Gearbox once. It provides a quick overview of active tasks and recent execution health.

From the desktop window you can:

- Create or edit automations with the same form
- Choose preset schedules or enter custom cron
- Preview the next scheduled runs before saving
- Switch between guided script selection and raw custom commands
- Set per-task shell, working directory, and environment variables

## Development

Gearbox consists of:
- **Core (Python)**: Task management, database (SQLite), and scheduling logic.
- **Daemon (Python)**: The background process that executes tasks.
- **CLI (Python/Click)**: Command-line interface.
- **UI (Swift)**: Native macOS menu bar application.

To build the UI manually:
```bash
./build_ui.sh
```

## Testing

### Python Backend
Testing is handled with `pytest`. To run the tests, use the provided virtual environment:
```bash
./venv/bin/python3 -m pytest tests/
```

### Swift UI
Testing is handled with `XCTest`. Run tests from the `GearboxUI` directory:
```bash
cd GearboxUI
swift test
```

## License

Standard Apache 2.0 License. See [LICENSE](LICENSE) for details.
