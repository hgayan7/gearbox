import pytest
import os
import sqlite3
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db import init_db
import core.db as db
import core.config as config

@pytest.fixture(autouse=True)
def test_db(tmp_path):
    # Override DB_PATH with a temporary file
    test_db_path = tmp_path / "test_gearbox.db"
    test_runtime_dir = test_db_path.parent
    original_db_path = config.DB_PATH
    original_gearbox_dir = config.GEARBOX_DIR
    config.DB_PATH = test_db_path
    config.GEARBOX_DIR = test_runtime_dir
    
    # Initialize the test database
    init_db()
    
    yield test_db_path
    
    # Reset DB_PATH
    config.DB_PATH = original_db_path
    config.GEARBOX_DIR = original_gearbox_dir
