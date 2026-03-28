import sqlite3
from sqlite3 import Connection
from . import config

def get_connection() -> Connection:
    """Returns a SQLite connection with row factory enabled."""
    config.ensure_runtime_paths()
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Initializes the SQLite database with the required schema."""
    config.ensure_runtime_paths()
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tasks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            command TEXT NOT NULL,
            schedule TEXT NOT NULL,
            is_paused INTEGER DEFAULT 0
        )
    ''')
    
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN schedule_desc TEXT")
    except sqlite3.OperationalError:
        pass
    
    # Runs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            exit_code INTEGER,
            stdout TEXT,
            stderr TEXT,
            pid INTEGER,
            FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE
        )
    ''')
    
    try:
        cursor.execute("ALTER TABLE runs ADD COLUMN pid INTEGER")
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    
    try:
        import cron_descriptor
        cursor.execute("SELECT id, schedule FROM tasks WHERE schedule_desc IS NULL")
        rows = cursor.fetchall()
        for row in rows:
            desc = cron_descriptor.get_description(row["schedule"])
            cursor.execute("UPDATE tasks SET schedule_desc = ? WHERE id = ?", (desc, row["id"]))
        conn.commit()
    except Exception:
        pass
    
    conn.close()

if __name__ == "__main__":
    init_db()
    print(f"Initialized Gearbox database at {config.DB_PATH}")
