import yaml
import os

class Config:
    __instance: dict = None
    @staticmethod
    def getInstance(file=None):
        if Config.__instance is None:
            Config.__instance: dict = yaml.load(file, yaml.CLoader)
            Config.__instance['debug'] = bool(os.environ.get('DEBUG', False))                                              
        return Config.__instance        
