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
    conn.commit()
    conn.close()


def add_event(chat_id: int, title: str, date: str, time: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO events (chat_id, title, date, time) VALUES (?, ?, ?, ?)",
        (chat_id, title, date, time),
    )
    conn.commit()
    conn.close()


def list_events(chat_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "SELECT title, date, time FROM events WHERE chat_id=? ORDER BY date, time",
        (chat_id,),
    )
    rows = c.fetchall()
    conn.close()
    return rows
