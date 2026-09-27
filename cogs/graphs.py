import datetime
import math
import time
from collections import Counter, defaultdict
from datetime import timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import patches
import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from config import ACTIVE_SERVER
from utils import iter_messages, save_graph, phrase_pattern, member_color

# timestamp of the first message ever logged
FIRST_MESSAGE_TIME = 1535451470
# 365 / 12 * 86400: the average number of seconds in a month
SECONDS_PER_MONTH = 2628000


def isenglishalpha(char):
    return char.isascii() and char.isalpha()


class Graphs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -- SEARCH GRAPH --

    @app_commands.command(name="searchgraph", description="create a bar graph of search results")
    @app_commands.describe(phrase = "What phrase to search for?")
    @app_commands.describe(nobots = "Defaults to True, set to False to have bot results show up in search")
    @app_commands.describe(fullwords = "Defaults to True, set to False to remove the full word filter")
    @app_commands.describe(normalize= "Defaults to False, set to True to normalize talking less")
    async def searchgraph(self, interaction, phrase: str, nobots: bool = True, fullwords: bool = True, normalize: bool = False):
        if '@everyone' in phrase or '@here' in phrase:
            await interaction.response.send_message('bro you really thought? naur...')
            return
        pattern = phrase_pattern(phrase, fullwords)
        await interaction.response.send_message(f'Searching for phrase \'{phrase}\'...')

        hits = Counter()       # authorID -> number of matches
        msgCount = Counter()   # authorID -> total messages
        for x in iter_messages():
            matches = pattern.findall(x.get("content"))
            if matches:
                hits[x.get("authorID")] += len(matches)
            msgCount[x.get("authorID")] += 1

        server = self.bot.get_guild(ACTIVE_SERVER)
        sortedSearchHits = []
        for key, val in hits.items():
            user = self.bot.get_user(key)
            if user is None:
                continue
            # nobots hides every bot; otherwise only this bot is hidden
            if (nobots and user.bot) or key == self.bot.user.id:
                continue
            value = 100 * val / msgCount[key] if normalize else val
            sortedSearchHits.append((value, user.name, member_color(server, key)))

        if not sortedSearchHits:
            await interaction.edit_original_response(content=f'no results for \'{phrase}\'')
            return

        # sort by number of hits, highest first
        sortedSearchHits.sort(key=lambda tup: tup[0], reverse=True)
        nummessages, people, colors = map(list, zip(*sortedSearchHits))
        figsizemod = len(people) / 8
        plt.figure(figsize=(6.4 * figsizemod, 4.8 * figsizemod))
        if not normalize:
            plt.title(f'How many times \'{phrase}\' was sent')
        else:
            plt.title(f'What percent of messages contain \'{phrase}\'?')
        ax = plt.gca()
        bars = ax.bar(people, nummessages, width=0.8)
        tick_labels = ax.get_xticklabels()
        ax.set_yticks([])
        for count, (label, bar) in enumerate(zip(tick_labels, bars), start=1):
            label.set_horizontalalignment('center')
            label.set_verticalalignment('bottom')
            label.set_fontweight('bold')
            label.set_fontfamily('monospace')
            label.set_fontsize('small')
            bar.set_color(colors[count - 1])
            if not normalize:
                bar_text = nummessages[count - 1]
            else:
                bar_text = str(round(nummessages[count - 1], 2)) + '%'
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), bar_text, ha='center', va='bottom')
            # stagger the name labels vertically so they don't overlap
            label.set_position((bar.get_x() + bar.get_width() / 2, (-0.02 / figsizemod) + (-0.05 / figsizemod) * (count % max(int(len(people) / 3), 1))))

        graph, embed = save_graph("searchgraph.png")
        await interaction.edit_original_response(embed=embed, attachments=[graph])

    # -- ALPHABET --

    @app_commands.command(name="alphabet", description="get a distribution of alphabetic characters for a user")
    @app_commands.describe(person = "which person will it be")
    @app_commands.describe(heatmap = "defaults to True, set to false to get a bar graph")
    async def alphabet(self, interaction, person: str, heatmap: bool = True):
        # count every english letter sent by `person`, and by the whole server for comparison
        await interaction.response.send_message('Searching...')
        frequency = defaultdict(int)
        serverfreq = defaultdict(int)
        charcount = 0
        servercharcount = 0
        for x in iter_messages():
            is_person = x.get("author") == person
            for char in x.get("content").casefold():
                if isenglishalpha(char):
                    serverfreq[char] += 1
                    servercharcount += 1
                    if is_person:
                        frequency[char] += 1
                        charcount += 1

        if heatmap:
            keyboard_layout = {
                'q': (0, 0), 'w': (0, 1), 'e': (0, 2), 'r': (0, 3), 't': (0, 4), 'y': (0, 5), 'u': (0, 6), 'i': (0, 7), 'o': (0, 8), 'p': (0, 9),
                'a': (1, 0), 's': (1, 1), 'd': (1, 2), 'f': (1, 3), 'g': (1, 4), 'h': (1, 5), 'j': (1, 6), 'k': (1, 7), 'l': (1, 8),
                'z': (2, 0), 'x': (2, 1), 'c': (2, 2), 'v': (2, 3), 'b': (2, 4), 'n': (2, 5), 'm': (2, 6)
            }
            # 3 x 10 grid shaped like a keyboard, filled with each letter's count
            formatteddata = np.zeros((3, 10))
            for key, val in frequency.items():
                row, col = keyboard_layout[key]
                formatteddata[row, col] = val

            plt.figure(figsize=(10, 3))
            plt.title(f'{person}\'s alphabet heatmap! wow so cool')
            plt.imshow(formatteddata, cmap='cool', interpolation='nearest')
            for char, (row, col) in keyboard_layout.items():
                plt.text(col, row, char.upper(), ha='center', va='center', color='black', fontfamily='monospace', fontweight='bold')
            plt.colorbar()
            plt.xticks([])
            plt.yticks([])
        else:
            # english letter frequencies (%), most common first
            wikinumchars = [12.7, 9.1, 8.2, 7.5, 7.0, 6.7, 6.3, 6.1, 6.0, 4.3, 4.0, 2.8, 2.8, 2.4, 2.4, 2.2, 2.0, 2.0, 1.9, 1.5, 1.0, 0.8, 0.2, 0.2, 0.1, 0.1]
            # every letter is included (even unused ones at 0%) so all three bar sets have 26 bars
            letters = 'abcdefghijklmnopqrstuvwxyz'
            listoftup = sorted(((100 * frequency[c] / max(charcount, 1), c) for c in letters), reverse=True)
            numchars, letter = map(list, zip(*listoftup))
            serverchars = sorted((100 * serverfreq[c] / max(servercharcount, 1) for c in letters), reverse=True)
            index = np.arange(26)
            plt.figure(figsize=(6.4 * 3, 4.8 * 3))
            plt.title(f'average letter frequency for {person}')
            ax = plt.gca()
            bar_width = 0.25
            ax.bar(index, numchars, bar_width, label=f'{person}', color='C0')
            ax.bar(index + bar_width, serverchars, bar_width, label='server', color='C1')
            ax.bar(index + (bar_width * 2), wikinumchars, bar_width, label='english', color='C2')
            ax.legend()
            ax.set_xticks(index + bar_width)
            ax.set_xticklabels([c.upper() for c in letter])

        graph, embed = save_graph("alphabet.png")
        await interaction.edit_original_response(embed=embed, attachments=[graph])

    # -- ACTIVITY HEAT MAP --

    @app_commands.command(name="activityheatmap", description="generate a heatmap")
    @app_commands.describe(type = "heatmap or line")
    async def activityheatmap(self, interaction, type: str = 'heatmap'):
        await interaction.response.send_message('lets do this shit!')
        # count messages sent in each ~month since the first message
        startTime = FIRST_MESSAGE_TIME
        messagesInMonth = 0
        monthList = []
        for z in iter_messages():
            if z.get("time") - startTime >= SECONDS_PER_MONTH:
                monthList.append(messagesInMonth)
                messagesInMonth = 0
                startTime = z.get("time")
            else:
                messagesInMonth += 1

        if type == 'heatmap':
            # one row per year, one column per month
            cols = 12
            rows = math.ceil(len(monthList) / cols)
            monthList += [0] * (rows * cols - len(monthList))
            hmData = np.array(monthList).reshape(rows, cols)
            plt.title('Activity heatmap of messages sent by month')
            plt.imshow(hmData, cmap='cool', interpolation='nearest', aspect='equal')
            plt.colorbar()
            plt.xlabel("Months passed")
            plt.ylabel("Years passed")
            for i, hmInt in enumerate(monthList):
                plt.text(i % cols, i // cols, hmInt, ha='center', va='bottom', color='black', fontfamily='monospace', fontweight='bold', fontsize = 7)
        elif type == 'line':
            plt.figure(figsize = (12,6))
            plt.plot(range(len(monthList)), monthList, color='r', marker='o', linewidth=2, label='Messages per Month')
            plt.title('Line graph of messages sent by month')
            plt.xlabel('Months passed')
            plt.ylabel('Number of messages sent')
            plt.grid(True)

        graph, embed = save_graph("activity.png")
        await interaction.edit_original_response(embed=embed, attachments=[graph])

    # -- TIME AVERAGE --

    @app_commands.command(name="timeaverage", description="unique words")
    async def timeaverage(self, interaction):
        await interaction.response.send_message('lets do this shit!')
        messagesDF = pd.DataFrame(iter_messages())
        pst = timezone(timedelta(hours=-8))
        messagesDF['hour'] = messagesDF['time'].apply(lambda x: datetime.datetime.fromtimestamp(x, tz=pst)).dt.hour
        messagesByHour = messagesDF['hour'].value_counts().sort_index()
        plt.figure(figsize=(10, 6))
        plt.title('Messages sorted by time sent')
        plt.bar(messagesByHour.index, messagesByHour.values)
        formattedHours = [f'{hour if hour != 0 else 24}:00' for hour in messagesByHour.index]
        plt.xticks(messagesByHour.index, formattedHours, fontsize=6)
        plt.xlabel('Hour of the day')
        plt.ylabel('Total messages sent')
        plt.grid(axis='y', alpha=0.7)

        graph, embed = save_graph("timeaverage.png")
        await interaction.edit_original_response(embed=embed, attachments=[graph])

    # -- NO LIFE GRAPH --

    @app_commands.command(name="nolifegraph", description="generate an up to date no life graph")
    @app_commands.describe(start_date = "Enter a date in the format MM/DD/YY. No response defaults to 08/01/2018")
    @app_commands.describe(end_date = "Enter a date in the format MM/DD/YY. No response defaults to current date")
    @app_commands.describe(minimum = "The minimum number of total messages someone needs to show up on the graph. Defaults to 1,000")
    @app_commands.describe(maximum = "The maximum number of total messages someone can have to show up on the graph. Defaults to 1,000,000")
    @app_commands.describe(person = "Filter to specific usernames. If entering multiple, separate with commas. Defaults to nobody")
    @app_commands.describe(word = "specific word to format graph around. leave blank for no specific word")
    async def nolifegraph(self, interaction, start_date: str = None, end_date: str = None, minimum: int = 1000, maximum: int = 1000000, person: str = None, word: str = None):
        # convert the MM/DD/YY inputs into datetimes / epoch timestamps (what message_history.json uses)
        try:
            # real start date is 2018/08/27 but 08/01 makes the graph look nicer
            start_date = datetime.datetime.strptime(start_date, '%m/%d/%y') if start_date else datetime.datetime(2018, 8, 1)
            end = datetime.datetime.strptime(end_date, '%m/%d/%y') if end_date else datetime.datetime.now()
        except ValueError as e:
            print('ValueError Raised:', e)
            await interaction.response.send_message("narr bro")
            return
        start_timestamp = time.mktime(start_date.timetuple())
        # add a day so every message sent on the end date itself is included
        date = time.mktime(end.date().timetuple()) + 86400

        if person:
            person = person.replace(' ', '').split(",")
        if word:
            pattern = phrase_pattern(word)
            if minimum == 1000:
                minimum = 0

        await interaction.response.send_message(content='Processing messages...')

        # author -> [total messages, {month number: messages that month}, authorID, time of first message]
        msgHistory = {}
        count = 0
        counting_started = False
        startTime = start_date
        for z in iter_messages():
            msg_time = z.get("time")
            if msg_time < start_timestamp:
                continue
            if date < msg_time:
                break
            if not counting_started:
                counting_started = True
                count = 1
            author = z.get("author")
            if not person or author in person:
                amount = len(pattern.findall(z.get("content"))) if word else 1
                entry = msgHistory.setdefault(author, [0, {}, z.get("authorID"), msg_time])
                entry[1][count] = entry[1].get(count, 0) + amount
                entry[0] += amount
            # move on to the next month once a month's worth of time has passed
            if msg_time - startTime.timestamp() >= SECONDS_PER_MONTH:
                count += 1
                startTime = datetime.datetime.fromtimestamp(msg_time)

        await interaction.edit_original_response(content='Generating the graph...')
        plt.title("No Life Graph")
        plt.xlabel("Date (MM/YY)")
        plt.ylabel("Number of Total Messages")
        ax = plt.gca()
        server = self.bot.get_guild(ACTIVE_SERVER)
        for ndict, (total, months, authorID, first_msg_time) in msgHistory.items():
            # skip old-style usernames with a #discriminator, and anyone outside the min/max range
            if "#" in ndict or not (maximum > total > minimum):
                continue
            member = server.get_member(authorID)
            if member is None:
                continue
            # running total of messages at each month
            w = []
            y = []
            oldval = 0
            for key, val in months.items():
                w.append(key)
                oldval += val
                y.append(oldval)
            # start each line at 0 the month before their first message
            w.insert(0, min(w) - 1)
            y.insert(0, 0)
            first_month = min(w)
            user_start = max(start_date, datetime.datetime.fromtimestamp(first_msg_time))
            x = np.array([user_start + relativedelta(months = i - first_month) for i in w])
            y = np.array(y)
            plt.plot(x, y, color=str(member.color), linewidth=2)
            plt.text(x[-1], y[-1], f'{ndict}')

        ax.set_ylim(bottom=0)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%y'))
        end_dt = datetime.datetime.fromtimestamp(date)
        date_range_months = (end_dt.year - start_date.year) * 12 + (end_dt.month - start_date.month)
        if date_range_months <= 6:
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        elif date_range_months <= 24:
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        else:
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
        ax.spines['right'].set_visible(False)
        ax.grid(axis='y', linewidth=1, alpha=0.8)
        ax.grid(which='major', axis='x', linewidth=0.5, alpha=0.25)
        plt.setp(ax.get_xticklabels(), rotation=60, ha='center')

        graph, embed = save_graph("nolifegraph.png")
        content = f'no life graph generated :3\ndate: {end_dt}\nminimum: {minimum}\n'
        if maximum != 1000000:
            content += f'maximum: {maximum}\n'
        content += f'specific word: {word or "no word specified"}'
        await interaction.edit_original_response(content=content, embed=embed, attachments=[graph])

    # -- TEST GRAPH --

    @app_commands.command(name="testgraph", description="this is a testing function for generating a graph")
    async def testgraph(self, interaction):
        plt.title(":8D:")
        plt.axis('off')
        fig = plt.gcf()
        ax = fig.gca()
        fig.set_facecolor('yellow')
        t = np.linspace(0, 2*np.pi, num=1000)
        x1 = (np.cos(t) / (np.sin(t) ** 2 + 1)) + 1
        y1 = np.cos(t) * np.sin(t) / (np.sin(t) ** 2 + 1)
        plt.plot(x1, y1, color='black', linewidth=6, fillstyle='full', gapcolor='white')
        ax.fill_between(x1, y1, color='white')
        x2 = np.array([0, 2])
        y2 = np.array([-0.5, -0.5])
        plt.plot(x2, y2, color='black', linewidth=6)
        x3 = np.linspace(0, 2, num=1000)
        y3 = (-1 * np.sqrt(((-1 * ((x3 - 1) ** 2)) + 1))) - 0.5
        plt.plot(x3, y3, color='black', linewidth=6)
        ax.fill_between(x3, y3, -0.5, color='white')
        ax.add_patch(patches.Circle((0.425, 0), 0.1, color='black', fill=True))
        ax.add_patch(patches.Circle((1.575, 0), 0.1, color='black', fill=True))

        graph, embed = save_graph("testgraph.png")
        await interaction.response.send_message(embed=embed, file=graph)


async def setup(bot):
    await bot.add_cog(Graphs(bot), guild=discord.Object(id=ACTIVE_SERVER))
