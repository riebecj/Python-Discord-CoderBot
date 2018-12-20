import discord
import base64
import requests
import pickle
import cloudpickle as cp
from urllib.request import urlopen
import dynmodule  # name of this module
import textwrap  # for more readable code formatting in sample string
import dateparser
import random
import asyncio
from datetime import datetime, timedelta
import discord
import json
import logging
import logging.config
import re
from signal import SIGINT, SIGTERM


log = logging.getLogger(__name__)
loop = asyncio.get_event_loop()


class Bot(object):
    def __init__(self):
        # Main parts of the bot
        self.token = 'TOKEN'
        self.prefix = '!'
        self.channel_lock = 'proving-grounds'
        self.client = discord.Client(loop=loop)
        self.commands = dict()
        self.supported_langs = None
        self.client.event(self.on_message)
        self._start_time = datetime.now()
        self.database = None
        self.title = None
        self.question = None
        self.test_cases = None
        self.answers = None
        self.set_commands()
        self.channels = None
        self.ongoing = False
        self.challenge_time = 0
        self.points = 0
        self.challenge_participants = None
        self.set_database()

    def set_commands(self):
        self.commands = {
            '!help': self._help,
            '!stats': self._stats,
            '!info': self._info,
            '!hello': self._greeting,
            '!schedule': self._schedule_event
        }

    def test_submission(self, user, submission):
        for test_case, answer in zip(self.test_cases, self.answers):
            if self.run(submission, test_case) == answer:
                continue
            else:
                return False
        return True

    def set_database(self):
        lang = 'python'
        self.database = {
            'python': 'python-data/questions'
        }
        self.supported_langs = self.database.keys()

    def run(self, func, *args):
        module_code = textwrap.dedent(func)
        dynmodule.load(module_code)  # defines module's contents
        return dynmodule.func(*args)

    async def end_challenge(self, channel):
        self.ongoing = False
        msg = 'That is the end of this Coding Challenge!\n Congratulations to {0.display_name} for ' \
              'scoring the most points!'.format()
        await self.client.send_message(channel, msg)

    async def begin_challenge(self, lang, channel):
        self.ongoing = True
        available = eval(open(self.database[lang.lower()], 'rt').read())
        selection = available[random.randint(0, len(available.keys()) - 1)]
        self.title = selection['title']
        self.question = selection['question']
        self.test_cases = selection['test_cases']
        self.answers = selection['answers']
        self.challenge_time = selection['time_limit']
        msg = "Welcome to the {} coding challenge!".format(lang)
        msg2 = 'A few rules before we begin...'
        msg3 = '1. All submission will be preceded by a `$`. This ensures I can parse it properly.'
        msg4 = "2. A correct answer will not end the contest, but award you points based upon how fast you submit " \
               "a correct answer."
        msg5 = "3. An incorrect answer will result in the wrong or invalid output (possibly traceback) being DM'ed " \
               "to you so you can work to correct your code."
        msg6 = "4. The initial part of the requested function will be given to you at the start of the challenge. " \
               "(e.g. `$def find_least_mean_square(listA, listB):`). This is to ensure proper execution and " \
               "validation on my end"
        msg7 = "You may either code in the Discord chat box (Hold `Shift` when pressing enter for a new line) or use " \
               "a text editor or your favorite IDE and copy/paste the code into the chat box."
        msg8 = "Now, without further ado, we begin in 5..."

        for msg in [msg, msg2, msg3, msg4, msg5, msg6, msg7, msg8]:
            await self.client.send_message(channel, msg)
            await asyncio.sleep(5)

        for i in range(4):
            await asyncio.sleep(1)
            await self.client.send_message(channel, "{}...".format(4-i))
        await self.client.send_message(channel, "\n{}\n\n{}".format(self.title, self.question))
        await self.challenge_timer(channel, self.challenge_time)


    def round_time(self, dt=None, round_to=60*60):
        """Round a datetime object to any time lapse in seconds
        dt : datetime.datetime object, default now.
        roundTo : Closest number of seconds to round to, default 1 minute.
        Author: Thierry Husson 2012 - Use it as you want but don't blame me.
        """
        if dt is None:
            dt = datetime.now()
        seconds = (dt.replace(tzinfo=None) - dt.min).seconds
        rounding = (seconds + round_to / 2) // round_to * round_to
        return dt + timedelta(0, rounding - seconds, -dt.microsecond)

    async def start(self):
        await self.client.login(self.token)

        try:
            await self.client.connect()
        except discord.ClientException:
            raise

    async def stop(self):
        await self.client.logout()

    async def on_message(self, message):
        if 'BotModerator' not in [role.name for role in message.author.roles]:
            return

        if message.channel.is_private:
            msg = 'Busy. Please stand by...'
            await self.client.send_message(message.channel, msg)
            return

        # we do not want the bot to reply to itself
        if message.author == self.client.user:
            return

        if message.channel.name != self.channel_lock:
            return

        if message.content.startswith('$'):
            if self.ongoing:
                await self.client.delete_message(message)
                msg = 'Thank you for your submission, {0.author.display_name}.'.format(message)
                self.test_submission(message.author, message.content)
            else:
                msg = "I'm sorry, {0.author.display_name}, " \
                      "but there is no active coding challenge at the moment.".format(message)
                await self.client.send_message(message.channel, msg)
                return

        if message.content.startswith(self.prefix):
            for command, func in self.commands.items():
                if command in message.content:
                    await func(message)
                    return

    # Commands
    async def _help(self, message):
        """Print the help message"""
        msg = 'Available commands:\n'
        for command, func in self.commands.items():
            msg += '`%s' % command
            msg += (' : %s`\n' % func.__doc__) if func.__doc__ else '`\n'

        await self.client.send_message(message.channel, msg)

    async def _schedule_event(self, message):
        """Create Coding Event (ex. !schedule Python in 3 days)"""
        msg_args = message.content.split(' ')
        if len(msg_args) < 3:
            await self.client.send_message(message.channel,
                                           "{0.display_name}, you're missing some arguments, my dear.".format(
                                               message.author))
            return
        else:
            sked_time = dateparser.parse(' '.join(msg_args[2:]))
            if sked_time is None:
                await self.client.send_message(message.channel,
                                               "`{}` is not a known time constraint.".format(sked_time))
                return
            else:
                lang = msg_args[1]
                if lang.lower() not in self.supported_langs:
                    await self.client.send_message(message.channel,
                                                   "`{}` is not a supported language.".format(lang))
                    return
            if self.round_time(sked_time, 60) == self.round_time(datetime.now(), 60):
                await self.begin_challenge(lang, message.channel)
                return
        self.client.loop.create_task(self.schedule_tracker(message, self.round_time(sked_time), lang))

    async def schedule_tracker(self, message, event_time, lang):
        idioms = ['Be there or be square!', 'Show up or shut up (respectfully)!', "Don't miss the boat!",
                  "You can't win if you don't play!", 'You snooze, you lose!']
        await self.client.wait_until_ready()
        channel = message.channel
        idiom = idioms[random.randint(0, len(idioms)-1)]
        msg = 'A `{}` coding challenge has been scheduled for {} PST.\n{}'.format(lang, event_time, idiom)
        await self.client.send_message(channel, msg)
        note1 = note2 = note3 = False
        while datetime.now() < event_time:
            days = (event_time - datetime.now()).days
            hours = (event_time - datetime.now()).hours
            minutes = (event_time - datetime.now()).minutes
            msg = '{} days, {} hours, and {} minutes until the  `{}` coding challenge!'.format(days, hours,
                                                                                               minutes, lang)
            await self.client.send_message(channel, msg)
            if days >= 1:
                await asyncio.sleep(60*60*12)
            elif hours >= 12:
                await asyncio.sleep(60 * 60 * 6)
            elif minutes >= 10:
                await asyncio.sleep(60 * 10)
        await self.begin_challenge(lang, channel)

    async def challenge_timer(self, channel, challenge_time):
        event_time = datetime.now() + timedelta(minutes=challenge_time)
        while datetime.now() < event_time:
            if self.challenge_time % 5 == 0:
                await self.client.send_message(channel, "{} remaining in this challenge".format(event_time-datetime.now()))
            await asyncio.sleep(60)
            self.challenge_time -= 1
        await self.end_challenge(channel)

    async def _info(self, message):
        """Print your id"""
        await self.client.send_message(message.channel, "{0.display_name}, Your id: `{0.id}`".format(message.author))

    async def _stats(self, message):
        """Show the bot's general stats"""
        users = -1
        for s in self.client.servers:
            users += len(s.members)
        msg = 'General informations:\n'
        msg += '`Uptime            : {} Seconds`\n'.format((datetime.now() - self._start_time).total_seconds())
        msg += '`Users in touch    : {} Users in {} servers`\n'.format(users, len(self.client.servers))
        msg += '`Cur Channel Lock  : #{}`'.format(self.channel_lock)
        await self.client.send_message(message.channel, msg)

    async def _greeting(self, message):
        """Say 'Hi' to the bot"""
        msg = 'Hello, {0.author.display_name}!'.format(message)
        await self.client.send_message(message.channel, msg)


if __name__ == '__main__':
    bot = Bot()

    asyncio.ensure_future(bot.start())
    loop.run_forever()

    loop.close()
