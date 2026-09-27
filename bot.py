# importing discord and commands
import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import time
import asyncio
import random
import io
from lz.reversal import reverse
import re
import csv

from config import (
    BOT_TOKEN, ACTIVE_SERVER,
    MESSAGE_FILE_PATH,
    EXTENSIONS, temp_path,
)

class EgirlsBot(commands.Bot):
    async def setup_hook(self):
        # runs once before the bot connects; loads every cog listed in config.EXTENSIONS
        for ext in EXTENSIONS:
            await self.load_extension(ext)

    async def on_message(self, message):
        # commands.Bot would normally try to run prefix commands here; this bot only uses
        # slash commands, so do nothing. Cogs still receive on_message through their listeners.
        pass


# slash commands setup
discord.VoiceClient.warn_nacl = False
mintents = discord.Intents.all()
# no prefix commands are used; the bot only exists for slash commands and events
client = EgirlsBot(command_prefix=commands.when_mentioned, intents=mintents, help_command=None)
tree = client.tree

# when bot is ready, prints the contents
@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=ACTIVE_SERVER))
    print("bot is ready")

# -- MYCOMMAND --

@tree.command(
    name="mycommand",
    description="My first application command",
    guild=discord.Object(id=ACTIVE_SERVER)
)
async def first_command(interaction):
    num = random.randint(1,20)
    if num > 1:
        await interaction.response.send_message("Hello!")
    else:
        await interaction.response.send_message(f'You are a gooner \ud83e\udef5')

@tree.command(
    name="8",
    description="8",
    guild=discord.Object(id=ACTIVE_SERVER)
)
async def eight(interaction):
    await interaction.response.send_message(f'🫡')

# -- REPEAT --

@tree.command(
    name="repeat",
    description="repeats what you say",
    guild=discord.Object(id=ACTIVE_SERVER)
)
@app_commands.describe(repeat = "What should be repeated?")
async def repeat(interaction, repeat: str):
    if '@everyone' in repeat or '@here' in repeat:
        await interaction.response.send_message(f'not here either man. im better')
        return
    await interaction.response.send_message(repeat)

# -- NUKE --

@tree.command(
    name="nuke",
    description="deletes a number of messages",
    guild=discord.Object(id=ACTIVE_SERVER)
)
@app_commands.describe(amount = "How many messages to delete? Maximum of 20")
async def nuke(interaction, amount: int):
    if amount < 21:
        await interaction.response.send_message(content=f'{amount} messages deleted', ephemeral=True)
        await interaction.channel.purge(limit=amount)
    else:
        await interaction.response.send_message(content=f'this command is capped at 20 messages at a time.', ephemeral=True)

# -- COINFLIP --

@tree.command(
    name="coinflip",
    description="flip a coin. any coin",
    guild=discord.Object(id=ACTIVE_SERVER)
)
@app_commands.describe(hidden = "Defaults to False, change to True to hide the coinflip from the world")
@app_commands.describe(numsides = "Defaults to 2. The number of sides to the coin")
async def coinflip(interaction, hidden: bool = False, numsides: int = 2):
    numsides = abs(numsides)
    try:
        num = random.randint(1,numsides)
        if(numsides == 2):
            if num == 1:
                await interaction.response.send_message("its heads bitch", ephemeral=hidden)
            else:
                await interaction.response.send_message("tails. bet u like tails. fury", ephemeral=hidden)
        else:
            formatted_num = format_numsides(num)
            await interaction.response.send_message(f'secret {formatted_num} side!', ephemeral=hidden)
    except ValueError as e:
        print('ValueError raised: ', e)
        await interaction.response.send_message(f'narr bro. dont zero')

def format_numsides(num):
    if num % 100 != 12 and num % 10 == 2:
        return f'{num}nd'
    elif num % 100 != 13 and num % 10 == 3:
        return f'{num}rd'
    elif num % 100 != 11 and num % 10 == 1:
        return f'{num}st'
    else:
        return f'{num}th'

# -- SECRET SANTA --

@tree.command(
    name="santa",
    description="its secret snata bro",
    guild=discord.Object(id=ACTIVE_SERVER)
)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(people = "enter a comma separated list of usernames")
async def santa(interaction, people: str):
    names = os.getenv("ALLOWED_PPL_NAMES")
    participants = []
    for mention in people.split(','):
        for member in interaction.guild.members:
            if member.name == mention.strip():
                participants.append(member)
    giftees = await fuckaroundandfindout(participants)
    finalpairs = dict(zip(participants, giftees))
    for gifter, giftee in finalpairs.items():
        giftee_name = names[giftee.name]
        try:
            await gifter.send(f'secret santa motherfuckers. you alraedy know whats up\n\nyour\'e person is: {giftee_name}')
        except discord.Forbidden:
            print(f'{gifter.name} needs to enable DMs')
    await interaction.response.send_message(f'sent out messages')
    return

async def fuckaroundandfindout(gifters):
    while True:
        giftees = gifters.copy()
        random.shuffle(giftees)
        if not any(gifters[i] == giftees[i] for i in range(len(gifters))):
            return giftees

# -- GET ALL MESSAGES --

CONCURRENT_CHANNEL_LIMIT = 3
semaphore = asyncio.Semaphore(CONCURRENT_CHANNEL_LIMIT)

@tree.command(
    name="getallmessages",
    description="gets every message sent and sorts them, and then stores them",
    guild=discord.Object(id=ACTIVE_SERVER)
)
@app_commands.checks.has_permissions(administrator=True)
async def getallmessages(interaction):
    # send a starter message
    await interaction.response.send_message(content=f'beginning message search', ephemeral=True)
    messageList = []
    server = client.get_guild(ACTIVE_SERVER)
    # create a task for every text channel in ACTIVE_SERVER
    taskList = [channelMessageCollector(chnl) for chnl in server.channels if str(chnl.type) == 'text']
    timeStart = time.time()
    # start running the tasks in taskList
    messageList = await asyncio.gather(*taskList)
    # flatten the list of lists into one single list
    allMessages = [msg for channelMsgs in messageList for msg in channelMsgs]
    timeEnd = time.time()
    print(f'{len(allMessages)} messages found and stored in allMessages, took {(timeEnd - timeStart):.2f} seconds')
    # begin sort
    timeStart = time.time()
    allMessagesSorted = sorted(allMessages, key = lambda msg: msg.created_at)
    timeEnd = time.time()
    print(f'{len(allMessagesSorted)} messages sorted, took {(timeEnd - timeStart):.2f} seconds')
    messageList.clear()
    # get all the essential information
    for msg in allMessagesSorted:
        msgDict = {
                "author": str(msg.author),
                "authorID": msg.author.id,
                "content": msg.content,
                "channel": str(msg.channel),
                "channelID": msg.channel.id,
                "msgID": msg.id,
                # subtracting 25200 because thats the number of seconds in 7 hours (utc to pst)
                "time": float(time.mktime((msg.created_at).timetuple()) - 25200)
        }
        messageList.append(msgDict)
    with open(MESSAGE_FILE_PATH, 'w') as f:
        for msg in messageList:
            json.dump(msg, f)
            f.write('\n')

async def channelMessageCollector(chnl):
    # make sure that no more processes than allowed are running
    async with semaphore:
        messageList = []
        timeList = []
        # only proceed with message gathering if the channel type is text
        timeStart = time.time()
        # run an initial history call to get the oldest 500 messages to establish the currentMessage variable
        async for msg in chnl.history(limit=40, oldest_first=True):
            messageList.append(msg)
        await asyncio.sleep(1)
        # set currentMessage to the most recently added message
        # could be a rare edge case where there's a channel with no messages
        currentMessage = messageList[-1] if messageList else None
        # once the last messages have been processed, currentMessage should be set to None
        while currentMessage:
            tempMessageList = []
            async for msg in chnl.history(limit=40, after=currentMessage, oldest_first=True):
                tempMessageList.append(msg)
            await asyncio.sleep(1)
            # exit loop if no messages were found
            if not tempMessageList:
                currentMessage = None
                timeEnd = time.time()
                timeList.append(timeEnd - timeStart)
            else:
                # add values from tempMessageList to messageList
                messageList.extend(tempMessageList)
                currentMessage = messageList[-1]
            # console info to amke sure everything is running
            if(len(messageList) % 3000 == 0):
                timeEnd = time.time()
                timeList.append(timeEnd - timeStart)
                print(f'channel: {chnl.name}, {len(messageList)}, took {timeList[-1]:.2f} seconds')
                timeStart = time.time()
        print(f'channel: {chnl.name} DONE, {len(messageList)} messages took {sum(timeList):.2f} seconds')
        return messageList

@tree.command(
    name="tempcommand",
    description="this is a command where i do things",
    guild=discord.Object(id=ACTIVE_SERVER)
)
@app_commands.checks.has_permissions(administrator=True)
async def tempcommand(interaction):
    # read the last 1000 messages, parse out the content, then create a dictionary with every
    # unique word in the content being a key and the value being that word's frequency
    content = {}
    num = 1
    count = 0
    with open(MESSAGE_FILE_PATH, 'r+') as f:
        for line in reverse(f, batch_size=io.DEFAULT_BUFFER_SIZE):
            if num > 1000:
                break
            num += 1
            words = re.findall(r'\b\w+\b', json.loads(line).get("content"))
            for word in words:
                if not word.isnumeric() and not ishex(word):
                    if word in content:
                        content[word] += 1
                    else:
                        content[word] = 1
                    count += 1
    with open(temp_path("wordfreq.csv"), 'w', newline = '') as f:
        writer = csv.writer(f)
        writer.writerow(['Word', 'Frequency'])
        for key,val in content.items():
            writer.writerow([key, val])
    await interaction.response.send_message(f'wrote last 1000 messages to csv file')

def ishex(nstring):
    try:
        int(nstring, 16)
        return True
    except ValueError:
        return False

# -- MISC --

@tree.command(
    name="yey",
    description="lol",
    guild=discord.Object(id=ACTIVE_SERVER)
)
async def yey(interaction):
    await interaction.response.send_message("YEY!!!!!!!!!!!!! LETS GO !!!! you are a stupid little bitch")

client.run(BOT_TOKEN)
