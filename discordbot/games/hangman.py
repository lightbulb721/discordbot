from discord.ext import commands
from discord import app_commands, Interaction
from dataclasses import dataclass, field, asdict
from discordbot.util import Store, Config
import datetime
import random
import sqlite3
import logging
from threading import Lock
import uuid
import openai
import requests


@dataclass
class HangmanModel:
    word: str = ''
    current: str = ''
    guesses: 'list' = field(default_factory=list)
    numGuesses: int = 0
    guildId: int = 0
    started: int = 0
    lastMove: int = 0
    hint: str = ''

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
        self.locks: dict[int, Lock] = {}
    
    def startup(self):
        self.conn = sqlite3.connect(self.file)
        try:
            cursor = self.conn.cursor()
            result = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='hangman';")
            item = result.fetchone()
            if item is None:
                cursor.execute(f"CREATE TABLE hangman(guildId integer primary key, word, current, numGuesses, started, lastMove, hint);")

            result = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='hangman_guesses';")
            item = result.fetchone()
            if item is None:
                cursor.execute(f"CREATE TABLE hangman_guesses(id integer primary key autoincrement, guildId, guess);")
        finally:
            cursor.close()
        

    def get(self, guildId: int, default=None):
        try:
            if guildId not in self.locks:
                self.locks[guildId] = Lock()
            self.locks[guildId].acquire()
            cursor = self.conn.cursor()
            result = cursor.execute("SELECT * from 'hangman' WHERE guildId=:guildId", {"guildId": guildId})
            item = result.fetchone()
            result = cursor.execute("SELECT guess from 'hangman_guesses' WHERE guildId=:guildId", {"guildId": guildId})
            guesses = [item[0] for item in result.fetchall()]
            if item is not None:
                return HangmanModel(guildId=item[0], word=item[1], current=item[2], numGuesses=item[3], started=item[4], lastMove=item[5], hint=item[6], guesses=guesses)
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
            cursor.execute("""INSERT INTO 'hangman' (word, current, numGuesses, guildId, started, lastMove, hint) VALUES(:word, :current, :numGuesses, :guildId, :started, :lastMove, :hint)
                              ON CONFLICT(guildId) DO UPDATE SET current=excluded.current, numGuesses=excluded.numGuesses, lastMove=excluded.lastMove, hint=excluded.hint""", d)
            cursor.execute("DELETE FROM 'hangman_guesses' WHERE guildId=:guildId", {"guildId": guildId})
            if len(guesses) > 0:
                cursor.executemany("INSERT INTO 'hangman_guesses'(guildId, guess) VALUES(:guildId, :guess)", [{"guildId": guildId, "guess": guess} for guess in guesses])
            self.conn.commit()
        finally:
            cursor.close()
    
    def free(self, guildId: int):
        self.locks[guildId].release()


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

    def __init__(self, store: HangmanDatabase, words: 'list[str]'):
        self.store = store
        self.config = Config.getInstance()
        self.words = words
        self.locks: dict[int, Lock] = {}

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
    
    def freeGame(self, guildId):
        self.store.free(guildId)

class HangmanGroup(app_commands.Group):
    pass

def get_synonym(word):
    messages = [{'role': 'user', 'content': f"Provide a synonym for the word '{word}' give me a sentence and don't use the word in the sentence:"}]
    response = openai.ChatCompletion.create(
      model="gpt-4",
      temperature=1.2,
      messages=messages,
      max_tokens=10
    )
    return response.choices[0].message.content.strip().lower()

def get_sentence(word, token):
    params = {
        'useCanonical': False,
        'api_key': token
    }
    headers = {
        'Accept': 'application/json'
    }
    response = requests.get(f'https://api.wordnik.com/v4/word.json/{word}/topExample', params=params, headers=headers)
    if not response.ok:
        raise Exception(f'Failed wordnik api request {response.status_code}')
    body = response.json()
    return body.get('text', '')

def register(bot: commands.Bot):
    group = HangmanGroup(name="hangman", description="play a game of hangman")
    config = Config.getInstance()

    @group.command(description="start a game of hangman")
    async def start(ctx: Interaction):
        try:
            if config['debug']:
                await ctx.response.defer()

            context = HangmanContext.getInstance()
            game = context.newGame(ctx.guild.id)
            await reply(ctx, str(game))
        except Exception as e:
            await logException(ctx, e, 'start')
        finally:
            context.freeGame(ctx.guild.id)

    @group.command(description="Get a hint from open ai and wordnik. Milage may vary 🙃")
    async def hint(ctx: Interaction):
        try:
            if config['debug']:
                await ctx.response.defer()

            context = HangmanContext.getInstance()
            game = context.getGame(ctx.guild.id)
            aiHint = str(get_synonym(game.word)).replace(game.word,"[Word Hidden]")
            logging.info(f'ai hint: {aiHint}')
            if game.hint == '':
                wordnikHint = get_sentence(game.word, config['wordnik_token']).replace(game.word, "[Word Hidden]")
                game.hint = wordnikHint
                logging.info(f'wordnik hint: {wordnikHint}')
                context.setGame(ctx.guild.id, game)
            else:
                wordnikHint = game.hint
            message = f'''
Chat-GPT hint
{aiHint}

===============================================================================
wordnik hint
{wordnikHint}
            '''
            await reply(ctx, message)
        except Exception as e:
            await logException(ctx, e, 'hint')
        finally:
            context.freeGame(ctx.guild.id)
        

    @group.command(description="guess a letter or word")
    async def guess(ctx: Interaction, guess: str):
        try:
            if config['debug']:
                await ctx.response.defer()
        
            context = HangmanContext.getInstance()
            game: HangmanModel = context.getGame(ctx.guild.id)
            guess = guess.lower()

            if game.numGuesses >= 6 or game.current == game.word:
                context.setGame(ctx.guild.id, None)
                await reply(ctx, f'Game over! The word was {game.word}\n{game}')
                return

            if len(guess) < 0:
                await reply(ctx, f'bad guess\n{game}')
                return

            if guess in game.guesses:
                await reply(ctx, f'guess: {guess} has already been guessed\n{game}')
                return
            
            if len(guess) > 1:
                if guess == game.word:
                    game.current = game.word
                    await reply(ctx, f'Win!\n{game}')
                    context.setGame(ctx.guild.id, None)
                    return
                else:
                    game.numGuesses += 1
                    game.guesses.append(guess)
                    if game.numGuesses >= 6:
                        context.setGame(ctx.guild.id, None)
                        await reply(ctx, f'Lose the word was {game.word}\n{game}')
                        return
                    context.setGame(ctx.guild.id, game)
                    await reply(ctx, f'Incorrect guess {guess}\n{game}')
                    return
                
            if guess not in game.word:
                game.numGuesses += 1
                game.guesses.append(guess)
                if game.numGuesses >= 6:
                    context.setGame(ctx.guild.id, None)
                    await reply(ctx, f'Lose the word was {game.word}\n{game}')
                    return
                context.setGame(ctx.guild.id, game)
                await reply(ctx, f'{guess} is not in the word\n{game}')
                return
            newWord = ''

            if len(game.word) != len(game.current):
                raise ValueError('Word and current guess are different lengths!')

            for i, char in enumerate(game.word):
                if char == guess:
                    newWord += guess
                else:
                    newWord += game.current[i]
            game.current = newWord
            if game.current == game.word:
                await reply(ctx, f'Win!\n{game}')
                context.setGame(ctx.guild.id, None)
                return
            context.setGame(ctx.guild.id, game)
            await reply(ctx, f'{guess} is in the word\n{game}')

        except ValueError as e:
            await logException(ctx, e, 'guess')
        except Exception as e:
            await logException(ctx, e, 'guess')
        finally:
            context.freeGame(ctx.guild.id)
        
    return group
async def logException(ctx: Interaction, e: Exception, call: str):
    id = uuid.uuid1()
    logging.exception(f'Id: {id} Exception guessing during {call} {e}')
    await reply(ctx, f'@lightbulb721 {call} {id} {e}')

async def reply(ctx: Interaction, message):
    if ctx.response.is_done():
        await ctx.followup.send(content=message)
    else:
        await ctx.response.send_message(message)