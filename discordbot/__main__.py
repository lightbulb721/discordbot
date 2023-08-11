import discord
from discordbot.server import BotClient
from discordbot.games import all
from discordbot.util import Config
import logging
import sys

def main():
    with open('data/config.yaml') as f:
        config = Config.getInstance(f)
    handler = logging.FileHandler(config['server']['logging']['file'], encoding='utf-8', mode='a')
    stdout = logging.StreamHandler(sys.stdout)
    logging.basicConfig(handlers=[handler, stdout])
    intents = discord.Intents.none()
    intents.guild_messages = True
    intents.dm_messages = True
    intents.dm_reactions = True
    intents.guild_reactions = True
    intents.message_content = True
    client = BotClient(command_prefix=config['server']['command_token'], intents=intents, logger=handler)
    for command in all:
        c = command(client)
        client.tree.add_command(c)
    client.run(config['server']['token'], log_handler=handler)

if __name__ == '__main__':
    main()