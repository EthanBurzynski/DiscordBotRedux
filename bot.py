import discord
from discord.ext import commands

from config import BOT_TOKEN, ACTIVE_SERVER, EXTENSIONS


class EgirlsBot(commands.Bot):
    async def setup_hook(self):
        # runs once before the bot connects; loads every cog listed in config.EXTENSIONS
        for ext in EXTENSIONS:
            await self.load_extension(ext)

    async def on_ready(self):
        # push the slash commands to the server so discord shows them
        await self.tree.sync(guild=discord.Object(id=ACTIVE_SERVER))
        print("bot is ready")

    async def on_message(self, message):
        # commands.Bot would normally try to run prefix commands here, but I only use slash commands, so this does nothing.
        pass


bot = EgirlsBot(command_prefix=commands.when_mentioned, intents=discord.Intents.all(), help_command=None)

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
