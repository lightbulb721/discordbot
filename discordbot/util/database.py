from discordbot.util.store import Store
import sqlite3
from dataclasses import asdict

class Database(Store):
    def __init__(self, file, table, columns):
        self.file = file
        self.table = table
        self.columns = columns
    
    def startup(self):
        self.conn = sqlite3.connect(self.file)
        try:
            cursor = self.conn.cursor()
            result = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';", {"table_name": self.table})
            items = result.fetchall()
            if len(items) < 0:
                cursor.execute(f"CREATE TABLE {self.table}({', '.join(self.columns)});")
        finally:
            cursor.close()
        

    def get(self, guildId: int, default=None, factory=lambda x: x):
        try:
            cursor = self.conn.cursor()
            result = cursor.execute("SELECT * from {table} WHERE guildId={guildId}", {'table': self.table, "guildId": guildId})
            item = result.fetchall()
            if len(item) > 0:
                item = item[0]
                return factory(item)
            else:
                return default
        finally:
            cursor.close()

    def set(self, guildId: int, item):
        d = asdict(item)
        d['table'] = self.table
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPSERT INTO {table} (" + ', '.join(self.columns) + ") VALUES("+ ', '.join(['{' + column + '}' for column in self.columns]) +")", d)
        finally:
            cursor.close()