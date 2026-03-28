import pytest
import sqlite3
from core.db import get_connection, init_db
import core.config as config
from pathlib import Path

def test_init_db(test_db):
    """Test that init_db creates the required tables."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if tasks table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
    assert cursor.fetchone() is not None
    
    # Check if runs table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'")
    assert cursor.fetchone() is not None
    
    conn.close()

def test_get_connection(test_db):
    """Test that get_connection returns a valid connection."""
    conn = get_connection()
    assert isinstance(conn, sqlite3.Connection)
    assert conn.row_factory == sqlite3.Row
    conn.close()


def test_init_db_normalizes_runtime_permissions(test_db):
    runtime_dir = Path(config.DB_PATH).parent
    runtime_dir.chmod(0o744)

    init_db()

    assert (runtime_dir.stat().st_mode & 0o777) == 0o700
