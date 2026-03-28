import os
from pathlib import Path

# Base directory for Gearbox
GEARBOX_DIR = Path.home() / ".gearbox"
DB_PATH = GEARBOX_DIR / "gearbox.db"

def ensure_runtime_paths():
    """Ensure runtime directories and files remain writable by the current user."""
    GEARBOX_DIR.mkdir(parents=True, exist_ok=True)

    try:
        os.chmod(GEARBOX_DIR, 0o700)
    except OSError:
        pass

    if DB_PATH.exists():
        try:
            os.chmod(DB_PATH, 0o600)
        except OSError:
            pass


ensure_runtime_paths()
