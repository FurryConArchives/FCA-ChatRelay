# Storage for processed message IDs and state
import sqlite3
from typing import Dict, Set, Optional

class StateRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_messages (
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                PRIMARY KEY (chat_id, message_id)
            )
        """)
        # For mapping between platforms
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS msgmap (
                fluxer_id TEXT,
                discord_id TEXT,
                telegram_id TEXT,
                author_id TEXT,
                guild_id TEXT
            )
        """)
        conn.commit()
        conn.close()

    def save_processed(self, chat_id: int, message_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO processed_messages (chat_id, message_id) VALUES (?, ?)",
            (chat_id, message_id)
        )
        conn.commit()
        conn.close()

    def load_processed(self) -> Dict[int, Set[int]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id, message_id FROM processed_messages")
        rows = cursor.fetchall()
        conn.close()
        processed = {}
        for chat_id, msg_id in rows:
            if chat_id not in processed:
                processed[chat_id] = set()
            processed[chat_id].add(msg_id)
        return processed

class MessageMapRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
    def save_mapping(self, fluxer_id: str, discord_id: str, telegram_id: str, author_id: str, guild_id: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO msgmap (fluxer_id, discord_id, telegram_id, author_id, guild_id) VALUES (?, ?, ?, ?, ?)",
            (fluxer_id, discord_id, telegram_id, author_id, guild_id)
        )
        conn.commit()
        conn.close()
    def get_discord_id_by_fluxer(self, fluxer_id: str) -> Optional[str]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT discord_id FROM msgmap WHERE fluxer_id = ?", (fluxer_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
