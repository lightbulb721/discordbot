class Store:
    def get(self, id, default):
        pass
    def set(self, id, item, factory: lambda x: x):
        pass
    def close(self):
        pass