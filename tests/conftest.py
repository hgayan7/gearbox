import pytest
import os
import sqlite3
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db import init_db
import core.db as db

@pytest.fixture(autouse=True)
def test_db(tmp_path):
    # Override DB_PATH with a temporary file
    test_db_path = tmp_path / "test_gearbox.db"
    original_db_path = db.DB_PATH
    db.DB_PATH = str(test_db_path)
    
    # Initialize the test database
    init_db()
    
    yield test_db_path
    
    # Reset DB_PATH
    db.DB_PATH = original_db_path
