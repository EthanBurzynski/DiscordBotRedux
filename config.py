"""Settings shared across the bot: env vars, file paths, and static data.

Nothing in here should import from bot.py or any cog, so every other
module can safely import from config.
"""
import os
from pathlib import Path
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

# bot token and twitter account info
BOT_TOKEN = os.getenv("BOT_TOKEN")
TWIKIT_USERNAME = os.getenv("TWITTER_USERNAME")
TWIKIT_EMAIL = os.getenv("TWITTER_EMAIL")
TWIKIT_PASSWORD = os.getenv("TWITTER_PASSWORD")
PROXY = os.getenv("PROXY")

# current server: egirls
ACTIVE_SERVER = int(os.getenv("ACTIVE_SERVER"))

# folders, relative to this file so the bot works no matter where it's launched from
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"      # persistent bot data (json logs, storage, cookies)
TEMP_DIR = BASE_DIR / "temp"      # generated images/files that get overwritten each run
ASSETS_DIR = BASE_DIR / "assets"  # static files the bot reads (lips.png, 1or2.png, songs)
SONGS_DIR = ASSETS_DIR / "songs"

DATA_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)


def data_path(name):
    return str(DATA_DIR / name)


def temp_path(name):
    return str(TEMP_DIR / name)


def asset_path(name):
    return str(ASSETS_DIR / name)


# data file paths
MESSAGE_FILE_PATH = data_path('message_history.json')
TWEET_FILE_PATH = data_path('tweet_storage.json')
TWEET_ID_FILE_PATH = data_path('tweet_id_storage.json')
TWIKIT_COOKIES_PATH = data_path('twikit_cookies.json')
DELETED_BOT_MESSAGES_FILE_PATH = data_path('deleted_bot_history.json')
COMMAND_HISTORY_FILE_PATH = data_path('command_history.json')
PLAYLIST_FILE_PATH = data_path('playlists.json')

# music file paths
SONG_DICT = {
    "1": str(SONGS_DIR / "clarity.mp3"), "2": str(SONGS_DIR / "godisagirl.mp3"), "3": str(SONGS_DIR / "shatterme.mp3"), "4": str(SONGS_DIR / "takeahint.mp3"),
    "5": str(SONGS_DIR / "elbeeper.mp3"), "6": str(SONGS_DIR / "willnotcomply.mp3"), "7": str(SONGS_DIR / "badhabits.mp3"), "8": str(SONGS_DIR / "howtobeaheartbreaker.mp3"),
    "9": str(SONGS_DIR / "freebird.mp3"), "10": str(SONGS_DIR / "itwasntme.mp3"), "11": str(SONGS_DIR / "nukeradio.mp3"), "12": str(SONGS_DIR / "onlygirlintheworld.mp3"),
    "13": str(SONGS_DIR / "peeisstoredintheballs.mp3"), "14": str(SONGS_DIR / "plok.mp3"), "15": str(SONGS_DIR / "resonance.mp3"), "16": str(SONGS_DIR / "rollermobster.mp3"),
    "17": str(SONGS_DIR / "turbokiller.mp3"), "18": str(SONGS_DIR / "youremine.mp3"), "19": str(SONGS_DIR / "streets112.mp3"), "20": str(SONGS_DIR / "relaxillhandleit.mp3"),
    "21": str(SONGS_DIR / "motivation.mp3"), "22": str(SONGS_DIR / "charliekirk.mp3"), "23": str(SONGS_DIR / "gigachadlofi.mp3")
}
SONG_DICT_NAMES = {
    "1": "Nightcore - Clarity", "2": "Nightcore - God is a Girl", "3": "Nightstep - Shatter Me", "4": "Nightcore - Take a Hint",
    "5": "El Beeper", "6": "I Will Not Comply", "7": "Bad Habits", "8": "Nightcore - How to be a Heartbreaker",
    "9": "Free Bird", "10": "It Wasn't Me", "11": "Nuke Radio", "12": "Only Girl in the World Hardstyle",
    "13": "Pee is Stored in the Balls", "14": "Plok! Overdrive Mix", "15": "Resonance", "16": "Roller Mobster",
    "17": "Turbo Killer", "18": "You're Mine", "19": "Streets 1:12", "20": "Relax. I\'ll Handle It",
    "21": "Get It Twisted", "22": "查理", "23": "Gigachad Theme Lofi"
}

# discord IDs used by the events cog
AUDIT_LOG_CHANNEL_ID = 1261771365539909674   # where audit log entries get posted
SUS_BOT_ID = 812172490256285747              # the "when the x is x sus" bot
SUS_BOT_IMMUNE_IDS = {731200697076547644, 164560262031081472}  # me, avery: sus bot replies to them get deleted
CORGAL_ID = 247858291760300032

# twt fetch retry limit
MAX_FETCH_RETRIES = 5

# cogs loaded at startup; add each new cog here as it's moved out of bot.py
EXTENSIONS = [
    "cogs.emoji",
    "cogs.twitter",
    "cogs.music",
    "cogs.graphs",
    "cogs.stats",
    "cogs.events",
]
