import pytest
import sqlite3
from core.db import get_connection, init_db
import core.config as config

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
