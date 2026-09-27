import asyncio
import json
import time

import discord
from discord import app_commands
from discord.ext import commands
from lz.reversal import reverse

from config import ACTIVE_SERVER, MESSAGE_FILE_PATH, temp_path

# how many channels /getallmessages reads at the same time
CONCURRENT_CHANNEL_LIMIT = 3


def ishex(nstring):
    try:
        int(nstring, 16)
        return True
    except ValueError:
        return False


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.semaphore = asyncio.Semaphore(CONCURRENT_CHANNEL_LIMIT)

    @app_commands.command(name="nuke", description="deletes a number of messages")
    @app_commands.describe(amount = "How many messages to delete? Maximum of 20")
    async def nuke(self, interaction, amount: int):
        if amount > 20:
            await interaction.response.send_message(content='this command is capped at 20 messages at a time.', ephemeral=True)
            return
        if amount < 1:
            await interaction.response.send_message(content='nothing to delete', ephemeral=True)
            return
        await interaction.response.send_message(content=f'{amount} messages deleted', ephemeral=True)
        await interaction.channel.purge(limit=amount)

    @app_commands.command(name="getallmessages", description="gets every message sent and sorts them, and then stores them")
    @app_commands.checks.has_permissions(administrator=True)
    async def getallmessages(self, interaction):
        """Re-downloads every message in every text channel and OVERWRITES message_history.json with them."""
        await interaction.response.send_message(content='beginning message search', ephemeral=True)
        server = self.bot.get_guild(ACTIVE_SERVER)

        # read every text channel (a few at a time, limited by the semaphore)
        timeStart = time.time()
        channels = [chnl for chnl in server.channels if str(chnl.type) == 'text']
        perChannel = await asyncio.gather(*(self.channelMessageCollector(chnl) for chnl in channels))
        allMessages = [msg for channelMsgs in perChannel for msg in channelMsgs]
        print(f'{len(allMessages)} messages found, took {(time.time() - timeStart):.2f} seconds')

        allMessages.sort(key=lambda msg: msg.created_at)
        with open(MESSAGE_FILE_PATH, 'w') as f:
            for msg in allMessages:
                json.dump({
                    "author": str(msg.author),
                    "authorID": msg.author.id,
                    "content": msg.content,
                    "channel": str(msg.channel),
                    "channelID": msg.channel.id,
                    "msgID": msg.id,
                    # UTC timestamp shifted back 7 hours (utc to pst), same as the events cog
                    "time": msg.created_at.timestamp() - 25200
                }, f)
                f.write('\n')
        await interaction.followup.send(f'done! stored {len(allMessages)} messages', ephemeral=True)

    async def channelMessageCollector(self, chnl):
        """reads a channel's whole history, oldest first, 40 messages per request"""
        async with self.semaphore:
            messageList = []
            timeStart = time.time()
            currentMessage = None
            try:
                while True:
                    batch = [msg async for msg in chnl.history(limit=40, after=currentMessage, oldest_first=True)]
                    await asyncio.sleep(1)
                    if not batch:
                        break
                    messageList.extend(batch)
                    currentMessage = messageList[-1]
                    # progress info so you can tell it's still running
                    if len(messageList) % 3000 == 0:
                        print(f'channel: {chnl.name}, {len(messageList)}, took {time.time() - timeStart:.2f} seconds')
            except discord.Forbidden:
                print(f'channel: {chnl.name} SKIPPED, no permission to read it')
                return []
            print(f'channel: {chnl.name} DONE, {len(messageList)} messages took {time.time() - timeStart:.2f} seconds')
            return messageList

    @app_commands.command(name="tempcommand", description="this is a command where i do things")
    @app_commands.checks.has_permissions(administrator=True)
    async def tempcommand(self, interaction):
        # this is a command that i edit whenever i want to satisfy some silly curiosity with the message data
        pass


async def setup(bot):
    await bot.add_cog(Admin(bot), guild=discord.Object(id=ACTIVE_SERVER))
