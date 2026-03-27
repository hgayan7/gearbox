# Contributing to Gearbox

Thank you for your interest in contributing to Gearbox! We welcome contributions of all kinds, from bug reports and feature requests to documentation improvements and code changes.

## How to Contribute

1.  **Fork the repository** on GitHub.
2.  **Clone your fork** locally.
3.  **Create a new branch** for your changes.
4.  **Make your changes** and ensure they follow the project's style.
5.  **Commit your changes** with clear, descriptive messages.
6.  **Push your branch** to your fork.
7.  **Submit a Pull Request** to the main repository.

## Reporting Bugs

If you find a bug, please create an issue on GitHub with:
- A clear description of the problem.
- Steps to reproduce the bug.
- Any relevant logs or screenshots.

## Homebrew Distribution

The repository includes a cask at `Casks/gearbox.rb`, but this repository is not a standalone Homebrew tap. User-facing install docs should point to the raw cask URL:

```bash
brew install --cask https://raw.githubusercontent.com/hgayan7/gearbox/main/Casks/gearbox.rb
```

If Gearbox later gets a dedicated tap, it should be published from a separate repository named `homebrew-gearbox` so `brew tap hgayan7/gearbox` works as expected.

## Code of Conduct

Please be respectful and professional in all interactions within the Gearbox community.
