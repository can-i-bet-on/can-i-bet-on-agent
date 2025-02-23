# TODO This is AI generated code. It's being used to store what betting pools we've generated in the past to avoid
# having the betting pool idea generator generate the same theme/idea twice in short succession.
# Move me to a preoper database/consider implementing a proper database later

import sqlite3
from datetime import datetime
from typing import List, Optional
import json


class BettingPoolDB:
    def __init__(self, db_path: str = "betting_pools.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS betting_pools (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    betting_pool_idea TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

    def add_betting_pool(self, topic: str, betting_pool_idea: dict):
        with sqlite3.connect(self.db_path) as conn:
            # Serialize the dictionary to JSON string
            betting_pool_json = json.dumps(betting_pool_idea)
            conn.execute(
                "INSERT INTO betting_pools (topic, betting_pool_idea) VALUES (?, ?)",
                (topic, betting_pool_json),
            )

    def get_recent_pools(self, limit: int = 5) -> List[tuple]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT topic, betting_pool_idea FROM betting_pools ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            # Deserialize JSON strings back to dictionaries
            results = cursor.fetchall()
            return [
                (topic, json.loads(betting_pool_idea))
                for topic, betting_pool_idea in results
            ]
