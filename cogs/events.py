import asyncio
import json
import os
import random
import re

import discord
from discord.ext import commands

from config import (
    ACTIVE_SERVER, DELETED_BOT_MESSAGES_FILE_PATH, COMMAND_HISTORY_FILE_PATH,
    AUDIT_LOG_CHANNEL_ID, SUS_BOT_ID, SUS_BOT_IMMUNE_IDS, CORGAL_ID,
)
from utils import append_message

RNGDLE_PATTERN = re.compile(r"rngdle\.com", re.IGNORECASE)
KEITH_STRING = "voidwhiteletsfuckinggo"


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -- message logging and reactions --

    @commands.Cog.listener()
    async def on_message(self, msg):
        msgStored = {
            "author": str(msg.author),
            "authorID": msg.author.id,
            "content": msg.content,
            "channel": str(msg.channel),
            "channelID": msg.channel.id,
            "msgID": msg.id,
            # UTC timestamp shifted back 7 hours (utc to pst); every existing entry uses this format
            "time": msg.created_at.timestamp() - 25200
        }
        if self.bot.user in msg.mentions and msg.author != self.bot.user:
            await msg.channel.send('sup bitch')
        await suppress_rngdle_embed(msg)

        if msg.author.id == SUS_BOT_ID and "when " in msg.content:
            await self.handle_sus_bot(msg, msgStored)
        elif msg.guild and msg.guild.id == ACTIVE_SERVER:
            append_message(msgStored)

        # shut up corgal
        if msg.author.id == CORGAL_ID and random.randint(1, 1000) == 1:
            await msg.channel.send("shut up kyglie")

        # keith test command thing: triggers if the letters of KEITH_STRING appear in order anywhere in the message
        count = 0
        for char in msg.content.casefold():
            if char == KEITH_STRING[count]:
                count += 1
            if count == len(KEITH_STRING):
                await msg.channel.send("OMNI HOLY SHIT!!!!!!")
                break

    async def handle_sus_bot(self, msg, msgStored):
        """"when the x is x sus" bot: auto-delete replies to certain people, otherwise let people vote it away"""
        # the message right before the sus bot's reply
        previous = [m async for m in msg.channel.history(limit=2)][1:]
        if previous and (previous[0].author.id in SUS_BOT_IMMUNE_IDS or previous[0].author.id == self.bot.user.id):
            await msg.delete()
            return

        await msg.add_reaction("❌")
        await asyncio.sleep(3)
        if msg.reactions[0].count > 1:
            # someone voted to delete it; credit everyone who reacted
            log = load_deleted_log()
            async for person in msg.reactions[0].users():
                if person.id != self.bot.user.id:
                    log[person.name] = log.get(person.name, 0) + 1
            with open(DELETED_BOT_MESSAGES_FILE_PATH, 'w') as f:
                json.dump(log, f)
            await msg.delete()
        else:
            await msg.clear_reactions()
            append_message(msgStored)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        # discord adds link embeds via an edit shortly after sending
        if after.embeds and not before.embeds:
            await suppress_rngdle_embed(after)

    # -- command usage tracking --

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction, command):
        # command_history.json has one line per user: {"username": {"command": count, ...}}
        history = {}
        if os.path.exists(COMMAND_HISTORY_FILE_PATH):
            with open(COMMAND_HISTORY_FILE_PATH, 'r') as f:
                for line in f:
                    history.update(json.loads(line))
        stats = history.setdefault(interaction.user.name, {})
        stats[command.name] = stats.get(command.name, 0) + 1
        with open(COMMAND_HISTORY_FILE_PATH, 'w') as f:
            for name, user_stats in history.items():
                json.dump({name: user_stats}, f)
                f.write('\n')

    # -- audit log --

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry):
        action_string = format_action(entry)
        channel = self.bot.get_channel(AUDIT_LOG_CHANNEL_ID)
        if action_string is None or channel is None:
            return
        await channel.send(f'{entry.user} {action_string}')


async def suppress_rngdle_embed(msg):
    # check the message text and any embed urls for the domain
    has_link = RNGDLE_PATTERN.search(msg.content or "") or any(
        e.url and RNGDLE_PATTERN.search(e.url) for e in msg.embeds
    )
    if has_link and not msg.flags.suppress_embeds:
        try:
            await msg.edit(suppress=True)
        except discord.Forbidden:
            print("Missing Manage Messages permission to suppress embeds")
        except discord.HTTPException as e:
            print(f"Failed to suppress embed: {e}")


def load_deleted_log():
    if not os.path.exists(DELETED_BOT_MESSAGES_FILE_PATH):
        return {}
    with open(DELETED_BOT_MESSAGES_FILE_PATH, 'r') as f:
        return json.load(f)


def format_action(entry):
    """describes an audit log entry in words, or returns None"""
    match entry.action.name:
        case "guild_update":
            return f'updated the server: {entry.after.__dict__}'
        case "channel_create":
            return f'created a {entry.after.type} channel #{entry.target}'
        case "channel_update":
            return f'made changes to #{entry.target}: {entry.after.__dict__}'
        case "channel_delete":
            return f'deleted the {entry.before.type} channel #{entry.before.name}'
        case "overwrite_create":
            return f'created a channel permission overwrite in #{entry.target} for {entry.extra}: {entry.after.__dict__}'
        case "overwrite_delete":
            return f'deleted a channel permission overwrite in #{entry.target} for {entry.extra}: {entry.after.__dict__}'
        case "kick":
            return f'kicked {entry.target.name} from the server'
        case "ban":
            return f'banned {entry.target.name} from the server'
        case "unban":
            return f'unbanned {entry.target.name} from the server'
        case "member_update":
            return f'updated {entry.target}: {entry.after.__dict__}'
        case "member_role_update":
            return f'updated {entry.target}\'s roles: {entry.after.__dict__}'
        case "member_move":
            return f'moved a member to {entry.extra.channel}'
        case "member_disconnect":
            return 'disconnected a member from a voice channel'
        case "role_create":
            return f'created a new role named {entry.after.name}'
        case "role_update":
            return f'updated the role named {entry.before.name}: {entry.after.__dict__}'
        case "role_delete":
            return f'deleted the role named {entry.before.name}'
        case "invite_create":
            return 'created a new invitation to the server'
        case "invite_update":
            return f'updated an invitation to the server: {entry.after.__dict__}'
        case "invite_delete":
            return 'deleted an invitation to the server'
        case "emoji_create":
            return f'created an emoji named {entry.after.name}'
        case "emoji_update":
            return f'updated the emoji named {entry.before.name}: {entry.after.__dict__}'
        case "emoji_delete":
            return f'deleted the emoji named {entry.before.name}'
        case "message_delete":
            return f'deleted {entry.extra.count} messages sent by {entry.target} in #{entry.extra.channel}'
        case "message_bulk_delete":
            return f'deleted {entry.extra.count} messages in #{entry.target}'
        case "message_pin":
            return f'pinned the message (ID: {entry.extra.message_id}) sent by {entry.target} to #{entry.extra.channel}'
        case "message_unpin":
            return f'unpinned the message (ID: {entry.extra.message_id}) sent by {entry.target} to #{entry.extra.channel}'
        case "sticker_create":
            return f'created a sticker named {entry.after.name}'
        case "sticker_update":
            return f'updated the sticker named {entry.before.name}: {entry.after.__dict__}'
        case "sticker_delete":
            return f'deleted the sticker named {entry.before.name}'
        case "thread_create":
            return f'created a thread named {entry.before.name}'
        case "thread_update":
            return f'updated a thread named {entry.before.name}'
        case "thread_delete":
            return f'deleted a thread named {entry.before.name}'
        case _:
            return None


async def setup(bot):
    await bot.add_cog(Events(bot))
