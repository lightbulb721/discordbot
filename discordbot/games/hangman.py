from discord.ext import commands
from discord import app_commands, Interaction
from dataclasses import dataclass, field, asdict
from discordbot.util import Store, Config
import datetime
import random
import sqlite3
import logging

import openai

openai.api_key = "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"



@dataclass
class HangmanModel:
    word: str = ''
    current: str = ''
    guesses: 'list' = field(default_factory=list)
    numGuesses: int = 0
    guildId: int = 0
    started: int = 0
    lastMove: int = 0

    def __str__(self):
        if self.numGuesses == 0:
            return f"""
```  +---+
  |   |
      |
      |    {self.current}
      |
      |    Guesses: {', '.join(self.guesses)}
=========
```"""
        elif self.numGuesses == 1:
            return f"""
```  +---+
  |   |
  O   |
      |    {self.current}
      |
      |    Guesses: {', '.join(self.guesses)}
=========
```"""
        elif self.numGuesses == 2:
            return f"""
```  +---+
  |   |
  O   |
  |   |    {self.current}
      |
      |    Guesses: {', '.join(self.guesses)}
=========
```"""
        elif self.numGuesses == 3:
            return f"""
```  +---+
  |   |
  O   |
 /|   |    {self.current}
      |
      |    Guesses: {', '.join(self.guesses)}
=========
```"""
        elif self.numGuesses == 4:
            return f"""
```  +---+
  |   |
  O   |
 /|\  |    {self.current}
      |
      |    Guesses: {', '.join(self.guesses)}
=========
```"""
        elif self.numGuesses == 5:
            return f"""
```  +---+
  |   |
  O   |
 /|\  |    {self.current}
 /    |
      |    Guesses: {', '.join(self.guesses)}
=========
```"""
        elif self.numGuesses >= 6:
            return f"""
```  +---+
  |   |
  O   |
 /|\  |    {self.current}
 / \  |
      |    Guesses: {', '.join(self.guesses)}
=========
```"""

class HangmanDatabase(Store):
    def __init__(self, file):
        self.file = file
    
    def startup(self):
        self.conn = sqlite3.connect(self.file)
        try:
            cursor = self.conn.cursor()
            result = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='hangman';")
            item = result.fetchone()
            if item is None:
                cursor.execute(f"CREATE TABLE hangman(guildId integer primary key, word, current, numGuesses, started, lastMove);")

            result = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='hangman_guesses';")
            item = result.fetchone()
            if item is None:
                cursor.execute(f"CREATE TABLE hangman_guesses(id integer primary key autoincrement, guildId, guess);")
        finally:
            cursor.close()
        

    def get(self, guildId: int, default=None):
        try:
            cursor = self.conn.cursor()
            result = cursor.execute("SELECT * from 'hangman' WHERE guildId=:guildId", {"guildId": guildId})
            item = result.fetchone()
            result = cursor.execute("SELECT guess from 'hangman_guesses' WHERE guildId=:guildId", {"guildId": guildId})
            guesses = [item[0] for item in result.fetchall()]
            if item is not None:
                return HangmanModel(guildId=item[0], word=item[1], current=item[2], numGuesses=item[3], started=item[4], lastMove=item[5], guesses=guesses)
            else:
                return default
        finally:
            cursor.close()

    def set(self, guildId: int, item):
        if item is None:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM 'hangman_guesses' WHERE guildId=:guildId", {"guildId": guildId})
                cursor.execute("DELETE FROM 'hangman' WHERE guildId=:guildId", {"guildId": guildId})
                self.conn.commit()
                return
            finally:
                cursor.close()

        d = asdict(item)
        guesses = d.pop('guesses')
        try:
            cursor = self.conn.cursor()
            cursor.execute("""INSERT INTO 'hangman' (word, current, numGuesses, guildId, started, lastMove) VALUES(:word, :current, :numGuesses, :guildId, :started, :lastMove)
                              ON CONFLICT(guildId) DO UPDATE SET current=excluded.current, numGuesses=excluded.numGuesses, lastMove=excluded.lastMove""", d)
            cursor.execute("DELETE FROM 'hangman_guesses' WHERE guildId=:guildId", {"guildId": guildId})
            if len(guesses) > 0:
                cursor.executemany("INSERT INTO 'hangman_guesses'(guildId, guess) VALUES(:guildId, :guess)", [{"guildId": guildId, "guess": guess} for guess in guesses])
            self.conn.commit()
        finally:
            cursor.close()


class HangmanContext:
    __instance = None

    @staticmethod
    def getInstance():
        if HangmanContext.__instance is None:
            with open('data/dictionary.txt') as f:
                words = [line.strip() for line in f.readlines()]
            store = HangmanDatabase('data/hangman.db')
            store.startup()
            HangmanContext.__instance = HangmanContext(store, words)
        return HangmanContext.__instance

    def __init__(self, store: Store, words: 'list[str]'):
        self.store = store
        self.config = Config.getInstance()
        self.words = words

    def newGame(self, guildId: int):
        game: HangmanModel = self.store.get(guildId)
        now = datetime.datetime.now(datetime.UTC).timestamp()
        if game is not None and now - game.lastMove < self.config['server']['hangman']['timeout']:
            return game
        game = HangmanModel(word=self.words[random.randint(
            0, len(self.words))], guildId=guildId, started=now, lastMove=now)
        game.current = '-' * len(game.word)
        self.store.set(guildId, game)
        return game
    
    def getGame(self, guildId: int):
        game = self.store.get(guildId)
        now = datetime.datetime.now(datetime.UTC).timestamp()
        if game is None or now - game.lastMove > self.config['server']['hangman']['timeout']:
            raise ValueError('No active game')
        game.lastMove = now
        self.store.set(guildId, game)
        return game

    def setGame(self, guildId: int, game: HangmanModel):
        game = self.store.set(guildId, game)

class HangmanGroup(app_commands.Group):
    pass

def get_synonym(word):
    response = openai.Completion.create(
      engine="davinci",
      prompt=f"Provide a synonym for the word '{word}':",
      max_tokens=10
    )
    return str(response.choices[0].text.strip())

def register(bot: commands.Bot):
    group = HangmanGroup(name="hangman", description="play a game of hangman")

    @group.command(description="start a game of hangman")
    async def start(ctx: Interaction):
        try:
            context = HangmanContext.getInstance()
            game = context.newGame(ctx.guild.id)
            await ctx.response.send_message(content=str(game))
        except Exception as e:
            logging.exception('Exception starting game', e)
            await ctx.response.send_message(content=f'@lightbulb721 {e}')

    @group.command(description="get a hint")
    async def hint(ctx: Interaction):
        try:
            context = HangmanContext.getInstance()
            game = context.newGame(ctx.guild.id)
            await ctx.response.send_message(content=str(get_synonym(game.word)).replace(game.word,"[Word Hidden]"))

    @group.command(description="guess a letter or word")
    async def guess(ctx: Interaction, guess: str):
        try:
            context = HangmanContext.getInstance()
            game: HangmanModel = context.getGame(ctx.guild.id)

            if game.numGuesses >= 6 or game.current == game.word:
                context.setGame(ctx.guild.id, None)
                await ctx.response.send_message(f'Game over! The word was {game.word}\n{game}')
                return

            if len(guess) < 0:
                await ctx.response.send_message(f'bad guess\n{game}')
                return
            
            if len(guess) > 1:
                if guess == game.word:
                    game.current = game.word
                    await ctx.response.send_message(f'Win!\n{game}')
                    context.setGame(ctx.guild.id, None)
                    return
                else:
                    game.numGuesses += 1
                    game.guesses.append(guess)
                    if game.numGuesses >= 6:
                        context.setGame(ctx.guild.id, None)
                        await ctx.response.send_message(f'Lose the word was {game.word}\n{game}')
                        return
                    context.setGame(ctx.guild.id, game)
                    await ctx.response.send_message(f'Incorrect guess {guess}\n{game}')
                    return
                
            if guess not in game.word:
                game.numGuesses += 1
                game.guesses.append(guess)
                if game.numGuesses >= 6:
                    context.setGame(ctx.guild.id, None)
                    await ctx.response.send_message(f'Lose the word was {game.word}\n{game}')
                    return
                context.setGame(ctx.guild.id, game)
                await ctx.response.send_message(f'{guess} is not in the word\n{game}')
                return
            newWord = ''
            for i, char in enumerate(game.word):
                if char == guess:
                    newWord += guess
                else:
                    newWord += game.current[i]
            game.current = newWord
            if game.current == game.word:
                await ctx.response.send_message(f'Win!\n{game}')
                context.setGame(ctx.guild.id, None)
                return
            context.setGame(ctx.guild.id, game)
            await ctx.response.send_message(f'{guess} is in the word\n{game}')
        except ValueError as e:
            logging.exception('Exception guessing during game', e)
            await ctx.response.send_message(str(e))
        except Exception as e:
            logging.exception('Exception guessing during game', e)
            await ctx.response.send_message(f'@lightbulb721 {e}')
        
    return group
