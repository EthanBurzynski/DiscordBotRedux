"""Small helpers used by more than one cog. Must not import from bot.py or cogs."""
import asyncio
import aiohttp


async def urllib_download(imgurl, filename):
    """
    Downloads an image from imgurl and saves it to filename.
    Retries up to 3 times with a 3-second delay between attempts.
    """
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
