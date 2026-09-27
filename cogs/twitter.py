import asyncio
import json
import os
import random

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image
from twikit import Client

from config import (
    ACTIVE_SERVER, TWEET_FILE_PATH, TWEET_ID_FILE_PATH, TWIKIT_COOKIES_PATH,
    MAX_FETCH_RETRIES, temp_path, asset_path,
)
from utils import urllib_download

# each bracket round: (votes_needed, enable_scaling, round_num, message shown before it starts)
TOURNAMENT_ROUNDS = [
    (5, True, 1, None),
    (6, True, 2, "ROUND ONE OVER !!! BEGINNING ROUND TWO IN THREE SECONDS..."),
    (7, True, 3, "ROUND TWO OVER !!! BEGINNING ROUND THREE IN THREE SECONDS..."),
    (7, False, 4, "TIME FOR THE FINAL BATTLE!!!"),
]


class Twitter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # logged-in twikit client, created on first use and reset if a fetch fails
        self.twikit_client = None

    @app_commands.command(name="twt", description="get twitter image. wow")
    async def twt(self, interaction):
        """
        picks random tweet from stored pool and displays it
        """
        await interaction.response.send_message("searching for image...")

        seen_ids = load_seen_ids()
        tweet_list = load_tweet_storage()

        # Refill the pool if it's running low
        if len(tweet_list) < 3:
            new_tweets, seen_ids = await self.refill_tweet_storage(seen_ids)
            tweet_list += new_tweets

        if not tweet_list:
            await interaction.edit_original_response(
                content="no new posts yet. stop gooning and wait a while"
            )
            return

        random.shuffle(tweet_list)
        chosen_tweet = tweet_list.pop(0)

        embed_author = discord.Embed()
        embed_author.set_author(
            name=f'from {chosen_tweet["username"]}:',
            url=chosen_tweet["url"]
        )

        # image embed (or fallback to lips.png if no image)
        if chosen_tweet["imgurl"] != "noimage":
            filename = temp_path("tweetimage.png")
            await urllib_download(chosen_tweet["imgurl"], filename)
            tweet_file = discord.File(filename)
            embed_image = discord.Embed()
            embed_image.set_image(url="attachment://tweetimage.png")
        else:
            tweet_file = discord.File(asset_path("lips.png"))
            embed_image = discord.Embed()
            embed_image.set_image(url="attachment://lips.png")

        # 1/50 chance of the gooner message
        if random.randint(1, 50) == 1:
            content = f"{interaction.user.name} is a gooner <:meowblush:846965478773882880>"
        else:
            content = None

        await interaction.edit_original_response(
            content=content,
            embeds=[embed_author, embed_image],
            attachments=[tweet_file]
        )

        save_tweet_storage(tweet_list)
        save_seen_ids(seen_ids)

    @app_commands.command(name="twttournament", description="tournament between 16 twitter images")
    async def twttournament(self, interaction):
        """
        pulls 16 random tweets from stored pool and runs a 4 round single-elim bracket
        """
        await interaction.response.send_message("searching for images...")

        seen_ids = load_seen_ids()
        all_tweets = load_tweet_storage()

        if len(all_tweets) < 16:
            new_tweets, seen_ids = await self.refill_tweet_storage(seen_ids)
            all_tweets += new_tweets

        if len(all_tweets) < 16:
            await interaction.edit_original_response(
                content="not enough stored tweets for a tournament"
            )
            return

        # Shuffle and take 16 for the tournament, save the rest back
        random.shuffle(all_tweets)
        remaining = all_tweets[:16]
        save_tweet_storage(all_tweets[16:])
        save_seen_ids(seen_ids)

        msg = await interaction.original_response()
        await msg.create_thread(name="tournament discussion")

        for votes_needed, enable_scaling, round_num, intro in TOURNAMENT_ROUNDS:
            if intro:
                await msg.edit(content=intro, embed=None, attachments=[])
                await asyncio.sleep(3)
            remaining = await tournament_helper(msg, remaining, votes_needed, enable_scaling, round_num)
            msg = await fetch_with_retries(msg)
            if msg is None:
                return
            if not remaining:
                await msg.edit(content="well thats no fun.", embed=None, attachments=[])
                return

        # Display the winner
        winner = remaining[0]
        embed_author = discord.Embed()
        embed_author.set_author(name=f'from {winner["username"]}:', url=winner["url"])

        await urllib_download(winner["imgurl"], temp_path("tweetimaget1.png"))
        tweet_file = discord.File(temp_path("tweetimaget1.png"))
        embed_image = discord.Embed()
        embed_image.set_image(url="attachment://tweetimaget1.png")

        await msg.edit(
            content="THE TOURNAMENT WINNER!",
            embeds=[embed_author, embed_image],
            attachments=[tweet_file]
        )

    # -- twikit --

    async def get_twikit_client(self):
        """
        returns authenticated twikit client
        """
        if self.twikit_client is not None:
            return self.twikit_client

        if not os.path.exists(TWIKIT_COOKIES_PATH):
            print("[twikit] ERROR: No cookies file found at", TWIKIT_COOKIES_PATH)
            print("[twikit] Export cookies from your browser and save them there.")
            raise FileNotFoundError(f"Missing {TWIKIT_COOKIES_PATH}")

        client = Client('en-US', impersonate='chrome124')
        client.load_cookies(TWIKIT_COOKIES_PATH)
        print("[twikit] Loaded cookies from file.")
        self.twikit_client = client
        return client

    async def refill_tweet_storage(self, seen_ids):
        """
        searches twitter for image tweets with more than 1500 likes from followed accounts, skips already seen images
        """
        new_tweets = []

        def add_results(results):
            for tweet in results:
                if tweet.id in seen_ids:
                    continue
                new_tweets.append(parse_tweet(tweet))
                seen_ids.add(tweet.id)

        try:
            twikit = await self.get_twikit_client()
            print(f"[twikit] Logged in as user ID: {await twikit.user_id()}")

            # "filter:follows" limits to your timeline, "filter:images" to tweets with
            # images, and "min_faves:1500" to popular tweets.
            search_results = await twikit.search_tweet(
                'filter:follows filter:images min_faves:1500',
                'Latest',
                count=40
            )
            add_results(search_results)

            # Try to get more results if we didn't get many
            if len(new_tweets) < 10 and search_results:
                try:
                    add_results(await search_results.next())
                except Exception as e:
                    print(f"[twikit] Could not fetch additional results: {e}")

            print(f"[twikit] Fetched {len(new_tweets)} new tweets.")

        except Exception as e:
            print(f"[twikit] Fetch failed: {e}")
            # Reset the client so next call will attempt a fresh login
            self.twikit_client = None

        return (new_tweets, seen_ids)


# -- tournament helpers --

async def fetch_with_retries(msg):
    """
    attempts to re-fetch a message up to MAX_FETCH_RETRIES times
    """
    for attempt in range(MAX_FETCH_RETRIES):
        try:
            return await msg.fetch()
        except (discord.DiscordServerError, TimeoutError):
            if attempt == MAX_FETCH_RETRIES - 1:
                return None
            await asyncio.sleep(10)


async def tournament_helper(msg, round_tweets, votes_needed, enable_scaling, round_num):
    """
    processes a list of tweets in pairs. for each pair, combine the two images, 
    post combined image with 1 and 2 as reactions, wait for enough votes, and winner advances
    """
    winners = []
    time_waited = 0        # counts 15-second intervals
    matchup_num = 1
    fetch_retries = 0

    while round_tweets:
        left_tweet = round_tweets.pop(0)
        right_tweet = round_tweets.pop(0)

        # -- Download and prepare both images --
        if left_tweet["imgurl"] != "noimage":
            await urllib_download(left_tweet["imgurl"], temp_path("tweetimaget1.png"))
            left_image = Image.open(temp_path("tweetimaget1.png"))
        else:
            left_image = Image.open(asset_path("lips.png"))

        if right_tweet["imgurl"] != "noimage":
            await urllib_download(right_tweet["imgurl"], temp_path("tweetimaget2.png"))
            right_image = Image.open(temp_path("tweetimaget2.png"))
        else:
            right_image = Image.open(asset_path("lips.png"))

        # -- Combine images: [LEFT] [1 or 2] [RIGHT], scaled to the left image's height --
        target_height = left_image.size[1]

        middle_image = Image.open(asset_path("1or2.png"))
        right_image = right_image.resize((
            int(right_image.size[0] * (target_height / right_image.size[1])),
            target_height
        ))
        middle_image = middle_image.resize((
            int(middle_image.size[0] * (target_height / middle_image.size[1])),
            target_height
        ))

        combined = Image.new('RGB', (
            left_image.size[0] + middle_image.size[0] + right_image.size[0],
            target_height
        ))
        combined.paste(left_image, (0, 0))
        combined.paste(middle_image, (left_image.size[0], 0))
        combined.paste(right_image, (left_image.size[0] + middle_image.size[0], 0))
        combined.save(temp_path("combinedtweetimage.png"))

        # -- Post the matchup --
        authors_text = (
            f'left image by: {left_tweet["username"]} | '
            f'right image by: {right_tweet["username"]}'
        )
        tweet_file = discord.File(temp_path("combinedtweetimage.png"))
        embed_image = discord.Embed()
        embed_image.set_image(url="attachment://combinedtweetimage.png")

        try:
            await msg.edit(content=authors_text, embeds=[embed_image], attachments=[tweet_file])
        except Exception as e:
            print(f"[tournament] Failed to edit message: {e}")

        # -- Add voting reactions --
        try:
            msg = await msg.fetch()
            fetch_retries = 0
        except (discord.DiscordServerError, TimeoutError) as e:
            print(f"[tournament] Server error on fetch: {e}")
            fetch_retries += 1
            if fetch_retries >= MAX_FETCH_RETRIES:
                return []
            await asyncio.sleep(10)
            continue
        except discord.HTTPException as e:
            print(f"[tournament] HTTP error on fetch: {e}")
            return []

        try:
            await msg.clear_reactions()
            await msg.add_reaction("1️⃣")
            await msg.add_reaction("2️⃣")
        except Exception as e:
            print(f"[tournament] Failed to set up reactions: {e}")

        # Re-fetch to get accurate reaction counts
        try:
            msg = await msg.fetch()
            fetch_retries = 0
        except (discord.DiscordServerError, TimeoutError) as e:
            print(f"[tournament] Server error on fetch: {e}")
            fetch_retries += 1
            if fetch_retries >= MAX_FETCH_RETRIES:
                return []
            await asyncio.sleep(10)
            continue
        except discord.HTTPException as e:
            print(f"[tournament] HTTP error on fetch: {e}")
            return []

        # Wait a moment for reactions to register
        await asyncio.sleep(5)

        if not _validate_reactions(msg):
            try:
                await msg.clear_reactions()
            except Exception:
                pass
            return []

        # -- Poll for votes until threshold is reached --
        current_threshold = votes_needed
        while (msg.reactions[0].count + msg.reactions[1].count) < current_threshold:
            await asyncio.sleep(15)
            time_waited += 1

            # After 30 minutes (120 intervals of 15s), lower the threshold if enabled
            if time_waited == 120 and enable_scaling:
                current_threshold -= 2

            # Update the message with vote progress every minute (4 intervals)
            if time_waited % 4 == 0:
                total_votes = msg.reactions[0].count + msg.reactions[1].count - 2
                needed_votes = current_threshold - 2
                try:
                    elapsed = time_waited * 15  # seconds
                    if elapsed < 3600:
                        time_str = f"{elapsed / 60:.0f} MINUTES ELAPSED"
                    else:
                        time_str = f"{elapsed / 3600:.2f} HOURS ELAPSED"

                    await msg.edit(
                        content=(
                            f"{authors_text}\n"
                            f"BRACKET: {round_num}   ROUND: {matchup_num}   {time_str}\n"
                            f"VOTES: {total_votes}/{needed_votes}"
                        )
                    )
                except Exception as e:
                    print(f"[tournament] Failed to update progress: {e}")

            # Re-fetch for updated reaction counts
            try:
                msg = await msg.fetch()
                fetch_retries = 0
            except (discord.DiscordServerError, TimeoutError) as e:
                print(f"[tournament] Server error during voting: {e}")
                fetch_retries += 1
                if fetch_retries >= MAX_FETCH_RETRIES:
                    return []
                await asyncio.sleep(10)
                continue
            except discord.HTTPException as e:
                print(f"[tournament] HTTP error during voting: {e}")
                return []

            # Re-validate reactions (someone might have removed them)
            if not _validate_reactions(msg):
                try:
                    await msg.clear_reactions()
                except Exception:
                    pass
                return []

        # -- Determine the winner of this matchup --
        left_votes = msg.reactions[0].count
        right_votes = msg.reactions[1].count

        if left_votes > right_votes:
            winners.append(left_tweet)
        elif right_votes > left_votes:
            winners.append(right_tweet)
        else:
            # Tie — pick randomly
            winners.append(random.choice([left_tweet, right_tweet]))

        time_waited = 0
        matchup_num += 1

        # Ping the channel to notify voters of the next matchup
        await msg.channel.send(
            content="plap plap plap get notified get notified get notified",
            delete_after=1.0
        )

    await msg.clear_reactions()
    return winners


def _validate_reactions(msg):
    """checks that the message's first two reactions are 1 and 2, in order"""
    if len(msg.reactions) < 2:
        return False
    return str(msg.reactions[0]) == "1️⃣" and str(msg.reactions[1]) == "2️⃣"


# -- tweet parsing and storage --

def parse_tweet(tweet):
    """turns a twikit tweet into the dict format stored in TWEET_FILE_PATH"""
    from twikit.media import Photo

    image_url = "noimage"
    for media_item in tweet.media or []:
        # grab the first photo's url
        if isinstance(media_item, Photo):
            image_url = media_item.media_url
            break

    # twikit doesn't provide a .url property, so build it manually
    username = tweet.user.screen_name
    return {
        "url": f"https://x.com/{username}/status/{tweet.id}",
        "imgurl": image_url,
        "username": username,
        "msgID": tweet.id,
    }


def save_tweet_storage(tweets):
    """overwrites TWEET_FILE_PATH with the given list of tweet dicts"""
    with open(TWEET_FILE_PATH, 'w') as f:
        for tweet in tweets:
            json.dump(tweet, f)
            f.write('\n')


def load_tweet_storage():
    """reads TWEET_FILE_PATH and returns a list of tweet dicts (url, imgurl, username, msgID)"""
    tweets = []
    if not os.path.exists(TWEET_FILE_PATH):
        return tweets
    with open(TWEET_FILE_PATH, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                tweets.append(json.loads(line))
    return tweets


def save_seen_ids(seen_ids):
    """overwrites TWEET_ID_FILE_PATH with the current set of seen IDs"""
    with open(TWEET_ID_FILE_PATH, 'w') as f:
        for tweet_id in seen_ids:
            json.dump({"msgID": tweet_id}, f)
            f.write('\n')


def load_seen_ids():
    """reads TWEET_ID_FILE_PATH ({"msgID": ...} per line) and returns the set of seen IDs"""
    seen = set()
    if not os.path.exists(TWEET_ID_FILE_PATH):
        return seen
    with open(TWEET_ID_FILE_PATH, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                seen.add(json.loads(line).get("msgID"))
    return seen


async def setup(bot):
    await bot.add_cog(Twitter(bot), guild=discord.Object(id=ACTIVE_SERVER))
