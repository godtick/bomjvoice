import sqlite3
import time
from .settings import APP_DIR


class History:
    def __init__(self):
        self.db = sqlite3.connect(str(APP_DIR / "history.db"), check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY, text TEXT, voice TEXT, ts INTEGER)")
        self.db.commit()

    def add(self, text, voice):
        # дубликаты не храним: такая же фраза просто поднимается наверх
        self.db.execute("DELETE FROM history WHERE text = ? AND voice = ?", (text, voice))
        self.db.execute("INSERT INTO history(text, voice, ts) VALUES(?,?,?)", (text, voice, int(time.time())))
        self.db.commit()

    def all(self, limit=500):
        return self.db.execute(
            "SELECT id, text, voice, ts FROM history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    def clear(self):
        self.db.execute("DELETE FROM history")
        self.db.commit()
