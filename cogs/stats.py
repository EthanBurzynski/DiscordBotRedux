import json
import os
from collections import Counter

import discord
from discord import app_commands
from discord.ext import commands

from config import ACTIVE_SERVER, DELETED_BOT_MESSAGES_FILE_PATH, COMMAND_HISTORY_FILE_PATH
from utils import iter_messages, phrase_pattern


def ranked_list(counts, limit=None):
    """formats {name: count} as a numbered list, highest count first"""
    ranked = sorted(((val, key) for key, val in counts.items()), reverse=True)[:limit]
    return "".join(f'{i}. {key}: {val}\n' for i, (val, key) in enumerate(ranked, start=1))


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="search", description="search for a word or phrase")
    @app_commands.describe(phrase = "What phrase to search for?")
    @app_commands.describe(nobots = "Defaults to True, set to False to have bot results show up in search")
    @app_commands.describe(fullwords = "Defaults to True, set to False to remove the full word filter")
    async def search(self, interaction, phrase: str, nobots: bool = True, fullwords: bool = True):
        if '@everyone' in phrase or '@here' in phrase:
            await interaction.response.send_message('bro you really thought? naur...')
            return
        pattern = phrase_pattern(phrase, fullwords)
        await interaction.response.send_message(f'Searching for phrase \'{phrase}\'...')

        hits = Counter()  # authorID -> number of matches
        for x in iter_messages():
            matches = pattern.findall(x.get("content"))
            if matches:
                hits[x.get("authorID")] += len(matches)

        results = []
        for key, val in hits.items():
            user = self.bot.get_user(key)
            if user is None:
                continue
            # nobots hides every bot; otherwise only this bot is hidden
            if (nobots and user.bot) or key == self.bot.user.id:
                continue
            results.append((val, user.name))

        if not results:
            await interaction.edit_original_response(content=f'nobody has said \'{phrase}\'. very sad')
            return
        totalnum = sum(val for val, _ in results)
        top_count, top_name = max(results)
        await interaction.edit_original_response(content=f'the phrase \'{phrase}\' came up {totalnum} times. it was sent the most times by {top_name} with {top_count} results.')

    @app_commands.command(name="scrape", description="scrape some data or smth")
    @app_commands.describe(person= "which person to get data for")
    async def scrape(self, interaction, person: str):
        totalchar = 0
        msgcount = 0
        for x in iter_messages():
            if x.get("author") == person:
                totalchar += len(x.get("content"))
                msgcount += 1
        if msgcount == 0:
            await interaction.response.send_message(f'no messages found for {person}')
            return
        await interaction.response.send_message(f'Average message length for {person}: {round((totalchar / msgcount), 3)}')

    @app_commands.command(name="whenthedeleteismany", description="get a top 10 list of who has deleted the sus bot messages the most")
    async def whenthedeleteismany(self, interaction):
        log = {}
        if os.path.exists(DELETED_BOT_MESSAGES_FILE_PATH):
            with open(DELETED_BOT_MESSAGES_FILE_PATH, 'r') as f:
                log = json.load(f)
        if not log:
            await interaction.response.send_message('nobody has deleted a sus bot message yet')
            return
        await interaction.response.send_message(ranked_list(log, limit=10))

    @app_commands.command(name="commandstats", description="gets a list of how many times each command has been used")
    @app_commands.describe(person = "which person to get stats for, defaults to nobody")
    async def commandstats(self, interaction, person: str = None):
        # command_history.json has one line per user: {"username": {"command": count, ...}}
        totals = Counter()
        if os.path.exists(COMMAND_HISTORY_FILE_PATH):
            with open(COMMAND_HISTORY_FILE_PATH, 'r') as f:
                for line in f:
                    for name, stats in json.loads(line).items():
                        if not person or name == person:
                            totals.update(stats)

        if not totals:
            await interaction.response.send_message(f'no command history found for {person}' if person else 'no command history found')
            return
        header = f'{person}\'s command stats:\n' if person else ''
        await interaction.response.send_message(header + ranked_list(totals))


async def setup(bot):
    await bot.add_cog(Stats(bot), guild=discord.Object(id=ACTIVE_SERVER))
