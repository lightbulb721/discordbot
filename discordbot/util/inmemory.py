from discordbot.util.store import Store

class InMemory(Store):
    def __init__(self):
        self.db = {}
    def get(self, guildId: int, default=None):
        return self.db.get(guildId, default)
    
    def set(self, guildId: int, item):
        self.db[guildId] = item