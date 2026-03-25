import os
from pathlib import Path

# Base directory for Gearbox
GEARBOX_DIR = Path.home() / ".gearbox"
DB_PATH = GEARBOX_DIR / "gearbox.db"

# Create the directory if it doesn't exist
GEARBOX_DIR.mkdir(parents=True, exist_ok=True)
