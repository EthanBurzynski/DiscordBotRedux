"""/emojine: combine two emojis into one image (or gif)."""
import math
import re

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageSequence

from config import ACTIVE_SERVER, temp_path
from utils import urllib_download


class Emoji(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="emojine", description="combine two emojis")
    @app_commands.describe(background_emoji = "an emoji, ideally (will not work if not an emoji so take that as you will)")
    @app_commands.describe(foreground_emoji = "an emoji, ideally (will not work if not an emoji so take that as you will)")
    @app_commands.describe(foreground_opacity = r"decimal number from 0.0 to 1.0 (0.9 being 90% opacity for example)")
    @app_commands.describe(foreground_scale = r"decimal number from 0.001 to 10.0 (0.9 being 90% scale for example)")
    @app_commands.describe(foreground_xoffset = r"decimal number from -2.0 to 2.0 (0.9 being 90% of the way to the right wall, for example)")
    @app_commands.describe(foreground_yoffset = r"decimal number from -2.0 to 2.0 (0.9 being 90% of the way to the top wall, for example)")
    async def emojine(self, interaction, background_emoji : str, foreground_emoji : str, foreground_opacity : float = 1.0, foreground_scale : float = 1.0, foreground_xoffset : float = 0.0, foreground_yoffset : float = 0.0):
        await interaction.response.send_message("thinkin real hard... real hard...")
        if (foreground_scale > 10.0 or foreground_scale < 0.001):
            foreground_scale = 1.0
        if (foreground_xoffset > 2.0 or foreground_xoffset < -2.0):
            foreground_xoffset = 0.0
        if (foreground_yoffset > 2.0 or foreground_yoffset < -2.0):
            foreground_yoffset = 0.0
        bg_url, bg_is_animated = getemojiurl(background_emoji)
        fg_url, fg_is_animated = getemojiurl(foreground_emoji)
        # downloading images
        if (bg_is_animated == 1):
            await urllib_download(bg_url, temp_path("emoji_bg.gif"))
        else:
            await urllib_download(bg_url, temp_path("emoji_bg.png"))
        if (fg_is_animated == 1):
            await urllib_download(fg_url, temp_path("emoji_fg.gif"))
        else:
            await urllib_download(fg_url, temp_path("emoji_fg.png"))

        # resizing and pasting logic
        if (bg_is_animated == 1 or fg_is_animated == 1):
            pastegif(temp_path("emoji_bg.gif") if bg_is_animated else temp_path("emoji_bg.png"), temp_path("emoji_fg.gif") if fg_is_animated else temp_path("emoji_fg.png"), foreground_opacity, foreground_scale, foreground_xoffset, foreground_yoffset)
            image_file = discord.File(temp_path("overlay.gif"))
            embed_file = discord.Embed()
            embed_file.set_image(url="attachment://overlay.gif")
        else:
            # opening images and resizing emojis to fit with the smallest emoji, then pasting
            bg_im = Image.open(temp_path("emoji_bg.png")).convert("RGBA")
            fg_im = Image.open(temp_path("emoji_fg.png")).convert("RGBA")
            bg_im, fg_im = resizetosmallest(bg_im, fg_im)
            r, g, b, a = fg_im.split()
            a = a.point(lambda p: int(p * foreground_opacity))
            fg_im = Image.merge("RGBA", (r, g, b, a))
            fg_im = fg_im.resize((math.ceil(fg_im.width * foreground_scale), math.ceil(fg_im.height * foreground_scale)))
            centered_pos = (
                int(((bg_im.width - fg_im.width) // 2) + (((bg_im.width / 2) - fg_im.width / 2) * foreground_xoffset)),
                int(((bg_im.height - fg_im.height) // 2) - (((bg_im.height / 2) - fg_im.height / 2) * foreground_yoffset))
            )
            bg_im.paste(fg_im, centered_pos, fg_im)
            # saving pasted image and sending to discord
            bg_im.save(temp_path("overlay.png"), format="PNG")
            image_file = discord.File(temp_path("overlay.png"))
            embed_file = discord.Embed()
            embed_file.set_image(url="attachment://overlay.png")

        await interaction.edit_original_response(content=None, embeds=[embed_file], attachments=[image_file])


# -- image helpers (plain functions; they don't need the bot) --

def pastegif(bg_fname, fg_fname, opacity, fg_scale, xoffset, yoffset):
    bg_im = Image.open(bg_fname)
    fg_im = Image.open(fg_fname)
    bg_frames = [frame.copy().convert("RGBA") for frame in ImageSequence.Iterator(bg_im)]
    fg_frames = [frame.copy().convert("RGBA") for frame in ImageSequence.Iterator(fg_im)]

    max_frames = max(len(bg_frames), len(fg_frames))
    final_gif = []
    for i in range(max_frames):
        bg_frame = bg_frames[i % len(bg_frames)]
        fg_frame = fg_frames[i % len(fg_frames)]

        bg_frame, fg_frame = resizetosmallest(bg_frame, fg_frame)
        r, g, b, a = fg_frame.split()
        a = a.point(lambda p: int(p * opacity))
        fg_frame = Image.merge("RGBA", (r, g, b, a))
        fg_frame = fg_frame.resize((math.ceil(fg_frame.width * fg_scale), math.ceil(fg_frame.height * fg_scale)))
        centered_pos = (
            int(((bg_frame.width - fg_frame.width) // 2) + (((bg_frame.width / 2) - fg_frame.width / 2) * xoffset)),
            int(((bg_frame.height - fg_frame.height) // 2) - (((bg_frame.height / 2) - fg_frame.height / 2) * yoffset))
        )
        bg_frame.paste(fg_frame, centered_pos, fg_frame)
        final_gif.append(bg_frame)

    duration = bg_im.info.get("duration") or fg_im.info.get("duration") or 100
    final_gif[0].save(temp_path("overlay.gif"), format="GIF", save_all=True, append_images = final_gif[1:], loop=0, duration=duration)


def resizetosmallest(bg_im, fg_im):
    # Determine smallest overall width/height between the two images
    bg_w, bg_h = bg_im.size
    fg_w, fg_h = fg_im.size
    target_dim = min(bg_w, fg_w, bg_h, fg_h)

    # scale image while preserving aspect ratio, so max(width, height) == target_dim
    def scale_to_fit(im, target_dim):
        w, h = im.size
        if w >= h:
            new_w = target_dim
            new_h = round(h * (target_dim / w))
        else:
            new_h = target_dim
            new_w = round(w * (target_dim / h))
        return im.resize((new_w, new_h))

    return scale_to_fit(bg_im, target_dim), scale_to_fit(fg_im, target_dim)


def getemojiurl(emoji: str):
    # regex expression to get emoji id and check if animated
    match = re.match(r'<(a?):(\w+):(\d+)>', emoji)
    if match:
        is_animated, emoji_name, emoji_id = match.groups()
        extension = 'gif' if is_animated else 'png'
        return f'https://cdn.discordapp.com/emojis/{emoji_id}.{extension}?v=1', 1 if is_animated else 0

    unicodeshit = '-'.join(f'{ord(char):x}' for char in emoji)
    return f'https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/{unicodeshit}.png', 0


async def setup(bot):
    # guild= makes every command in this cog guild-only, same as guild=... on @tree.command
    await bot.add_cog(Emoji(bot), guild=discord.Object(id=ACTIVE_SERVER))
