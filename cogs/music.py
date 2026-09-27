import ast
import asyncio
import json
import os
from typing import List

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button

from config import ACTIVE_SERVER, PLAYLIST_FILE_PATH, SONG_DICT, SONG_DICT_NAMES


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.playlists = {}      # playlist name -> list of song IDs (ints)
        self.queue = []          # song IDs (strings) waiting to play; loops forever
        self.current_song = None  # song ID currently playing

    async def cog_load(self):
        # runs once when the cog is loaded, before the bot connects
        self.load_playlists()

    # -- playlist file --

    def load_playlists(self):
        self.playlists = {}
        if not os.path.exists(PLAYLIST_FILE_PATH):
            return
        with open(PLAYLIST_FILE_PATH, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    x = json.loads(line)
                    self.playlists[x.get("name")] = x.get("songs")

    def save_playlists(self):
        with open(PLAYLIST_FILE_PATH, 'w') as f:
            for key, val in self.playlists.items():
                json.dump({"name": key, "songs": val}, f)
                f.write('\n')

    def playlist_exists(self, name):
        return name.lower() in (key.lower() for key in self.playlists.keys())

    def reset_queue(self):
        self.queue = []
        self.current_song = None

    # -- autocompletes --

    async def song_autocomplete(self, interaction, current: str) -> List[app_commands.Choice[str]]:
        matches = [(songID, name) for songID, name in SONG_DICT_NAMES.items() if current.lower() in name.lower()]
        return [app_commands.Choice(name=name, value=songID) for songID, name in matches[:25]]

    async def playlist_autocomplete(self, interaction, current: str) -> List[app_commands.Choice[str]]:
        # value is the playlist's song list as a string, e.g. "[1, 4, 7]"; vcplay parses it back
        matches = [(name, songs) for name, songs in self.playlists.items() if current.lower() in name.lower()]
        return [app_commands.Choice(name=name, value=str(songs)) for name, songs in matches[:25]]

    async def playlistname_autocomplete(self, interaction, current: str) -> List[app_commands.Choice[str]]:
        matches = [name for name in self.playlists.keys() if current.lower() in name.lower()]
        return [app_commands.Choice(name=name, value=name) for name in matches[:25]]

    def _songs_matching(self, interaction, current, in_playlist):
        """song choices filtered by whether they're in the playlist chosen in the 'playlistname' option"""
        playlistname = None
        for option in interaction.data.get("options", []):
            if option.get("name") == "playlistname":
                playlistname = option.get("value")
                break
        if playlistname not in self.playlists:
            return []
        songs = self.playlists[playlistname]
        choices = []
        for songID, songname in SONG_DICT_NAMES.items():
            if (int(songID) in songs) == in_playlist and current.lower() in songname.lower():
                choices.append(app_commands.Choice(name=songname, value=songID))
        return choices[:25]

    async def specificplaylist_autocomplete(self, interaction, current: str) -> List[app_commands.Choice[str]]:
        return self._songs_matching(interaction, current, in_playlist=True)

    async def specificplaylistNOT_autocomplete(self, interaction, current: str) -> List[app_commands.Choice[str]]:
        return self._songs_matching(interaction, current, in_playlist=False)

    # -- playlist commands --

    @app_commands.command(name="createplaylist", description="throughout heaven and earth i alone have the best music taste")
    @app_commands.autocomplete(songchoice=song_autocomplete)
    async def createplaylist(self, interaction, playlistname: str, songchoice: str):
        if songchoice not in SONG_DICT:
            await interaction.response.send_message('alright coral.')
            return
        if self.playlist_exists(playlistname):
            await interaction.response.send_message('playlist name already exists')
            return
        self.playlists[playlistname] = [int(songchoice)]
        self.save_playlists()
        await interaction.response.send_message(f'created playlist `{playlistname}`. go u')

    @app_commands.command(name="addtoplaylist", description="j-janky command t-to edit pwaywists~! >w<")
    @app_commands.autocomplete(playlistname=playlistname_autocomplete, songchoice=specificplaylistNOT_autocomplete)
    async def addtoplaylist(self, interaction, playlistname: str, songchoice: str):
        if not self.playlist_exists(playlistname):
            await interaction.response.send_message('not a real playlist. you must not be a real playlist editer. fake fan')
            return
        if songchoice not in SONG_DICT:
            await interaction.response.send_message("it's impressive that you got here")
            return
        self.playlists[playlistname].append(int(songchoice))
        self.save_playlists()
        await interaction.response.send_message(f'edited playlist `{playlistname}`, added song `{SONG_DICT_NAMES[songchoice]}`')

    @app_commands.command(name="listplaylists", description="if ur reading this ur looking cute today")
    async def listplaylists(self, interaction):
        if not self.playlists:
            await interaction.response.send_message('somehow the playlists variable is empty. this is not supposed to be possible. dm me if this message appears')
            return
        await send_paginated(interaction, list(self.playlists.keys()), "playlists")

    @app_commands.command(name="listsongs", description="necessary evil my behated")
    async def listsongs(self, interaction):
        await send_paginated(interaction, list(SONG_DICT_NAMES.values()), "songs")

    @app_commands.command(name="listplaylistsongs", description="hi")
    @app_commands.autocomplete(playlistname=playlistname_autocomplete)
    async def listplaylistsongs(self, interaction, playlistname: str):
        if not self.playlist_exists(playlistname):
            await interaction.response.send_message('not a real playlist. you must not be a real playlist editer. fake fan')
            return
        songnames = [SONG_DICT_NAMES[str(songID)] for songID in self.playlists[playlistname]]
        await send_paginated(interaction, songnames, "songs in playlist")

    @app_commands.command(name="deleteplaylist", description="hated it that much?")
    @app_commands.autocomplete(playlistname=playlistname_autocomplete)
    async def deleteplaylist(self, interaction, playlistname: str):
        if not self.playlist_exists(playlistname):
            await interaction.response.send_message('not a real playlist. you must not be a real playlist editer. fake fan')
            return
        del self.playlists[playlistname]
        self.save_playlists()
        await interaction.response.send_message(f'removed `{playlistname}` from the list')

    @app_commands.command(name="editplaylist", description="FUCK that song in particular")
    @app_commands.autocomplete(playlistname=playlistname_autocomplete, songchoice=specificplaylist_autocomplete)
    async def editplaylist(self, interaction, playlistname: str, songchoice: str):
        if not self.playlist_exists(playlistname):
            await interaction.response.send_message('not a real playlist. you must not be a real playlist editer. fake fan')
            return
        if songchoice not in SONG_DICT:
            await interaction.response.send_message('hi chis')
            return
        songID = int(songchoice)
        if songID not in self.playlists[playlistname]:
            await interaction.response.send_message('alright coral.')
            return
        self.playlists[playlistname].remove(songID)
        # delete the playlist if that was its last song
        if not self.playlists[playlistname]:
            del self.playlists[playlistname]
            self.save_playlists()
            await interaction.response.send_message(f'last song removed, deleted `{playlistname}` from the list')
            return
        self.save_playlists()
        await interaction.response.send_message(f'removed `{SONG_DICT_NAMES[songchoice]}` from `{playlistname}`')

    # -- voice commands --

    @app_commands.command(name="testvc", description="test voice connection")
    async def testvc(self, interaction):
        if not interaction.user.voice:
            await interaction.response.send_message("Join a voice channel first")
            return
        channel = interaction.user.voice.channel
        try:
            await interaction.response.send_message("Attempting to connect...")
            vc = await channel.connect(timeout=30.0)
            await interaction.followup.send("Connected successfully!")
            await asyncio.sleep(2)
            await vc.disconnect()
        except Exception as e:
            await interaction.followup.send(f"Connection failed: {str(e)}")
            print(f"Full error details: {e}")

    @app_commands.command(name="vcplay", description="discover what if does for urself :3")
    @app_commands.autocomplete(playlist=playlist_autocomplete)
    async def vcplay(self, interaction, playlist: str):
        self.reset_queue()
        songIDs = ast.literal_eval(playlist)
        # make sure author is in vc
        if not interaction.user.voice:
            await interaction.response.send_message('join a voice channel first bozo')
            return
        channel = interaction.user.voice.channel
        vc = interaction.guild.voice_client
        # connect to vc, or move vc
        if vc and vc.is_connected():
            await vc.disconnect()
            await asyncio.sleep(1)
        vc = await channel.connect()
        await interaction.response.send_message('going playlist mode')
        # load the song IDs into the queue
        for songID in songIDs:
            songID = str(songID)
            if songID in SONG_DICT and songID in SONG_DICT_NAMES:
                self.queue.append(songID)
        # begin the audio loop
        if not vc.is_playing():
            await self.play_next(vc, None)

    async def play_next(self, vc, e):
        if e:
            print(f'error on that thang: {e}')
        # nothing to play, or we've been disconnected (vcstop / everyone left)
        if not self.queue or not vc.is_connected():
            return
        # take the song at the front of the queue and move it to the back, so the playlist loops
        self.current_song = self.queue.pop(0)
        self.queue.append(self.current_song)
        audio_source = discord.FFmpegPCMAudio(SONG_DICT[self.current_song])
        # vc.play's `after` callback runs in another thread, so hand play_next back to the bot's event loop
        loop = self.bot.loop
        vc.play(audio_source, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(vc, e), loop))

    @app_commands.command(name="vcpause", description="figure it out")
    async def vcpause(self, interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            await interaction.response.send_message('no song playing lil bro')
            return
        vc.pause()
        await interaction.response.send_message('paused the audio. just for u. i would do anything for you')

    @app_commands.command(name="vcresume", description="the sequel to pausing")
    async def vcresume(self, interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_paused():
            await interaction.response.send_message('what are you doing')
            return
        vc.resume()
        await interaction.response.send_message('YEAHHHHHHHHHH LETS GET THIS PARTY FUCKING GOING!!!!!!!!!!!')

    @app_commands.command(name="vcstop", description="makes bot leave vc and stop audio")
    async def vcstop(self, interaction):
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.response.send_message('so hatefu;l??')
            return
        # clear the queue first, so when vc.stop() triggers play_next there's nothing left to play
        self.reset_queue()
        vc.stop()
        await vc.disconnect()
        await interaction.response.send_message('bye bey !')

    @app_commands.command(name="vcskip", description="you dont need this")
    async def vcskip(self, interaction):
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.response.send_message('fuck u doin bro')
            return
        # grab the name before stopping, since vc.stop() immediately starts the next song
        skipped = SONG_DICT_NAMES.get(self.current_song)
        vc.stop()
        await interaction.response.send_message(f"skipped {skipped}")

    @app_commands.command(name="vcqueue", description="lists queue")
    async def vcqueue(self, interaction):
        if not self.queue:
            await interaction.response.send_message('aint nothing here lil bro')
            return
        queue_message = "\n".join(f"{index + 1}. {SONG_DICT_NAMES[songID]}" for index, songID in enumerate(self.queue))
        await interaction.response.send_message(f"Song queue:\n{queue_message}")

    # -- events --

    @commands.Cog.listener()
    async def on_ready(self):
        # leave any voice channels left over from before a restart/reconnect
        for vc in self.bot.voice_clients:
            await vc.disconnect(force=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        vc = member.guild.voice_client
        if vc and vc.channel:
            non_bots = [m for m in vc.channel.members if not m.bot]
            # if no real people are left in vc, stop and leave
            if not non_bots and (vc.is_playing() or vc.is_paused()):
                self.reset_queue()
                vc.stop()
                await vc.disconnect()


# -- paginated list embeds --

async def send_paginated(interaction, items, title):
    """sends an embed listing 'items', 10 per page, with previous/next buttons"""
    view = PaginatedListView(items, title, timeout=60)
    await interaction.response.send_message(embed=view.build_embed(), view=view)
    view.message = await interaction.original_response()


class PaginatedListView(View):
    def __init__(self, items, title, timeout=60):
        super().__init__(timeout=timeout)
        self.items_list = items
        self.title = title
        self.current_page = 0
        self.total_pages = max(1, (len(items) + 9) // 10)
        self.message = None
        self.update_buttons()

    def build_embed(self):
        start_index = self.current_page * 10
        page_items = self.items_list[start_index:start_index + 10]
        description = "\n".join(f"{start_index + index + 1}. {item}" for index, item in enumerate(page_items))
        embed = discord.Embed(title=self.title, description=description, color=discord.Color.blurple())
        embed.set_footer(text=f'Page {self.current_page + 1}/{self.total_pages}')
        return embed

    def update_buttons(self):
        self.clear_items()
        if self.current_page > 0:
            back_button = Button(style=discord.ButtonStyle.primary, emoji="⬅️", label="previous")
            back_button.callback = self.go_back
            self.add_item(back_button)
        if self.current_page < self.total_pages - 1:
            forward_button = Button(style=discord.ButtonStyle.primary, emoji="➡️", label="next")
            forward_button.callback = self.go_forward
            self.add_item(forward_button)

    async def go_back(self, interaction):
        self.current_page -= 1
        await self.update_message(interaction)

    async def go_forward(self, interaction):
        self.current_page += 1
        await self.update_message(interaction)

    async def update_message(self, interaction):
        self.update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_timeout(self):
        # remove the buttons once they stop working
        self.clear_items()
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


async def setup(bot):
    await bot.add_cog(Music(bot), guild=discord.Object(id=ACTIVE_SERVER))
