"""SQLite connection factory for EBL. Schema initialization remains in server.py.
"""
import sqlite3

from ebl_config import DB

def conn():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=30000")
    return c
