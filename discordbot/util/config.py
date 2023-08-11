import yaml

class Config:
    __instance = None
    @staticmethod
    def getInstance(file=None):
        if Config.__instance is None:
            Config.__instance = yaml.load(file, yaml.CLoader)
        return Config.__instance
        
