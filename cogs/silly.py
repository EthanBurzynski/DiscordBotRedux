import ast
import os
import random

import discord
from discord import app_commands
from discord.ext import commands

from config import ACTIVE_SERVER


def format_numsides(num):
    """1 -> 1st, 2 -> 2nd, 3 -> 3rd, 11 -> 11th, etc."""
    if num % 100 != 12 and num % 10 == 2:
        return f'{num}nd'
    elif num % 100 != 13 and num % 10 == 3:
        return f'{num}rd'
    elif num % 100 != 11 and num % 10 == 1:
        return f'{num}st'
    else:
        return f'{num}th'


def fuckaroundandfindout(gifters):
    """Shuffles gifters until nobody is assigned to themselves. Needs at least 2 people."""
    while True:
        giftees = gifters.copy()
        random.shuffle(giftees)
        if not any(gifter == giftee for gifter, giftee in zip(gifters, giftees)):
            return giftees


def load_santa_names():
    """
    ALLOWED_PPL_NAMES in .env maps discord usernames to the name shown in the santa DM
    """
    raw = os.getenv("ALLOWED_PPL_NAMES")
    if not raw:
        return {}
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        print("[santa] ALLOWED_PPL_NAMES in .env isn't a valid dictionary")
        return {}


class Silly(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mycommand", description="My first application command")
    async def first_command(self, interaction):
        if random.randint(1, 20) > 1:
            await interaction.response.send_message("Hello!")
        else:
            await interaction.response.send_message('You are a gooner 🫵')

    @app_commands.command(name="8", description="8")
    async def eight(self, interaction):
        await interaction.response.send_message('🫡')

    @app_commands.command(name="yey", description="lol")
    async def yey(self, interaction):
        await interaction.response.send_message("YEY!!!!!!!!!!!!! LETS GO !!!! you are a stupid little bitch")

    @app_commands.command(name="repeat", description="repeats what you say")
    @app_commands.describe(repeat = "What should be repeated?")
    async def repeat(self, interaction, repeat: str):
        if '@everyone' in repeat or '@here' in repeat:
            await interaction.response.send_message('not here either man. im better')
            return
        await interaction.response.send_message(repeat)

    @app_commands.command(name="coinflip", description="flip a coin. any coin")
    @app_commands.describe(hidden = "Defaults to False, change to True to hide the coinflip from the world")
    @app_commands.describe(numsides = "Defaults to 2. The number of sides to the coin")
    async def coinflip(self, interaction, hidden: bool = False, numsides: int = 2):
        numsides = abs(numsides)
        if numsides == 0:
            await interaction.response.send_message('narr bro. dont zero')
            return
        num = random.randint(1, numsides)
        if numsides == 2:
            if num == 1:
                await interaction.response.send_message("its heads bitch", ephemeral=hidden)
            else:
                await interaction.response.send_message("tails. bet u like tails. fury", ephemeral=hidden)
        else:
            await interaction.response.send_message(f'secret {format_numsides(num)} side!', ephemeral=hidden)

    @app_commands.command(name="santa", description="its secret snata bro")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(people = "enter a comma separated list of usernames")
    async def santa(self, interaction, people: str):
        requested = [name.strip() for name in people.split(',') if name.strip()]
        members_by_name = {member.name: member for member in interaction.guild.members}
        participants = [members_by_name[name] for name in requested if name in members_by_name]
        not_found = [name for name in requested if name not in members_by_name]
        if len(participants) < 2:
            await interaction.response.send_message('need at least 2 real people for secret santa', ephemeral=True)
            return

        # sending DMs can take a while, so tell discord we're working on it
        await interaction.response.defer()
        names = load_santa_names()
        giftees = fuckaroundandfindout(participants)
        no_dms = []
        for gifter, giftee in zip(participants, giftees):
            giftee_name = names.get(giftee.name, giftee.display_name)
            try:
                await gifter.send(f'secret santa motherfuckers. you alraedy know whats up\n\nyour\'e person is: {giftee_name}')
            except discord.Forbidden:
                print(f'{gifter.name} needs to enable DMs')
                no_dms.append(gifter.name)

        result = 'sent out messages'
        if not_found:
            result += f'\ncouldn\'t find: {", ".join(not_found)}'
        if no_dms:
            result += f'\ncouldn\'t DM (they need to enable DMs): {", ".join(no_dms)}'
        await interaction.followup.send(result)


async def setup(bot):
    await bot.add_cog(Silly(bot), guild=discord.Object(id=ACTIVE_SERVER))
