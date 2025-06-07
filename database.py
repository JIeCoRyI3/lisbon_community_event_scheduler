import sqlite3

DB_NAME = "events.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        title TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL
    )"""
    )
    # Ensure location column exists for backward compatibility
    c.execute("PRAGMA table_info(events)")
    columns = [row[1] for row in c.fetchall()]
    if "location" not in columns:
        c.execute("ALTER TABLE events ADD COLUMN location TEXT")
    # Table for event applications
    c.execute(
        """CREATE TABLE IF NOT EXISTS event_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER,
        username TEXT,
        UNIQUE(event_id, username)
    )"""
    )
    conn.commit()
    conn.close()


def add_event(chat_id: int, title: str, date: str, time: str, location: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO events (chat_id, title, date, time, location) VALUES (?, ?, ?, ?, ?)",
        (chat_id, title, date, time, location),
    )
    conn.commit()
    conn.close()


def list_events(chat_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "SELECT title, date, time, location FROM events WHERE chat_id=? ORDER BY date, time",
        (chat_id,),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def list_events_with_ids(chat_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "SELECT id, title, date, time, location FROM events WHERE chat_id=? ORDER BY date, time",
        (chat_id,),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def delete_event(event_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM events WHERE id=?", (event_id,))
    c.execute("DELETE FROM event_applications WHERE event_id=?", (event_id,))
    conn.commit()
    conn.close()


def apply_to_event(event_id: int, username: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO event_applications (event_id, username) VALUES (?, ?)",
        (event_id, username),
    )
    conn.commit()
    conn.close()


def cancel_application(event_id: int, username: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "DELETE FROM event_applications WHERE event_id=? AND username=?",
        (event_id, username),
    )
    conn.commit()
    conn.close()


def list_applicants(event_id: int) -> list[str]:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "SELECT username FROM event_applications WHERE event_id=? ORDER BY username",
        (event_id,),
    )
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows


def is_applied(event_id: int, username: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM event_applications WHERE event_id=? AND username=?",
        (event_id, username),
    )
    row = c.fetchone()
    conn.close()
    return row is not None


def get_event(event_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "SELECT id, chat_id, title, date, time, location FROM events WHERE id=?",
        (event_id,),
    )
    row = c.fetchone()
    conn.close()
    return row
