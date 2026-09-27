# bunch of small helper functions used across cogs
import asyncio
import json
import re

import aiohttp
import discord
import matplotlib
matplotlib.use("Agg")  # render graphs to files only; never try to open a window
import matplotlib.pyplot as plt

from config import MESSAGE_FILE_PATH, temp_path


async def urllib_download(imgurl, filename):
    # downloads an image from imgurl and saves it to filename, retrying up to 3 times
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(imgurl) as response:
                    if response.status == 200:
                        with open(filename, 'wb') as f:
                            f.write(await response.read())
                        return True
                    else:
                        print(f"[download] Attempt {attempt + 1}: HTTP {response.status} for {imgurl}")
        except Exception as e:
            print(f"[download] Attempt {attempt + 1}: Error downloading {imgurl}: {e}")

        if attempt < 2:
            await asyncio.sleep(3)

    print(f"[download] Failed to download {imgurl} after 3 attempts.")
    return False


def iter_messages():
    # gives every logged message from message_history.json, starting from the oldest, as a dict with keys (author, authorID, content, channel, channelID, msgID, time)
    with open(MESSAGE_FILE_PATH, 'r') as f:
        for line in f:
            yield json.loads(line)


def append_message(message_dict):
    # appends one message to message_history.json
    with open(MESSAGE_FILE_PATH, 'a') as f:
        json.dump(message_dict, f)
        f.write('\n')


def phrase_pattern(phrase, fullwords=True):
    # case insensitive regex for a phrase
    flags = re.IGNORECASE
    if not fullwords:
        return re.compile(phrase, flags)
    if phrase.isalnum():
        return re.compile(fr'\b{phrase}\b', flags)
    return re.compile(fr'(?<!\w){phrase}(?!\w)', flags)


def member_color(guild, user_id):
    # get a member's role color as a hexadecimal string
    member = guild.get_member(user_id)
    return str(member.color if member else discord.Color.default())


def save_graph(name):
    # saves current matplotlib figure to temp/[name] and closes it, returns (file, embed)
    filename = temp_path(name)
    plt.savefig(filename, bbox_inches='tight')
    plt.close()
    embed = discord.Embed()
    embed.set_image(url=f"attachment://{name}")
    return discord.File(filename), embed
