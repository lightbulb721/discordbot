from typing import Any, Optional, Type
from discord.ext import commands
from discord import app_commands, Intents
from discord.ext.commands.bot import PrefixType, _default
from discord.ext.commands.help import HelpCommand
import logging


class BotClient(commands.Bot):
    def __init__(self, command_prefix: PrefixType, *, logger: logging.Handler, help_command: HelpCommand | None = ..., tree_cls: Type[app_commands.CommandTree[Any]] = app_commands.CommandTree, description: str | None = None, intents: Intents, **options: Any) -> None:
        super().__init__(command_prefix, help_command=help_command, tree_cls=tree_cls, description=description, intents=intents, **options)
        self.logger = logger
    async def on_ready(self):
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        logging.info(f'Logged in as {self.user} (ID: {self.user.id})')
