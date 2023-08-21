import yaml
import os
from dotenv import load_dotenv

class Config:
    __instance: dict = None
    @staticmethod
    def getInstance(file=None):
        if Config.__instance is None:
            Config.__instance: dict = yaml.load(file, yaml.CLoader)
            load_dotenv(Config.__instance['server'].get('env', '.env'))
            Config.__instance['debug'] = bool(os.environ.get('DEBUG', False))
            Config.__instance['discord_token'] = os.environ.get('DISCORD_TOKEN')
            Config.__instance['openai_token'] = os.environ.get('OPENAI_TOKEN')      
            Config.__instance['wordnik_token'] = os.environ.get('WORDNIK_TOKEN')                                   
        return Config.__instance        
