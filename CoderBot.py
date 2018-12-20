import discord
import base64
import requests
import pickle
import cloudpickle as cp
from urllib.request import urlopen
import dynmodule  # name of this module
import textwrap  # for more readable code formatting in sample string
import dateparser

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
        self.token = ''
        self.prefix = '!'
        self.channel_lock = 'proving-grounds'
        self.authenticator = ''
        self.client = discord.Client(loop=loop)
        self.commands = dict()
        self.supported_langs = ['python']
        self.client.event(self.on_message)
        self._start_time = datetime.now()
        self.database = None
        self.question = None
        self.test_cases = None
        self.answers = None
        self.set_commands()
        self.channels = None

    def set_commands(self):
        self.commands = {
            '!help': self._help,
            '!stats': self._stats,
            '!info': self._info,
            '!hello': self._greeting,
            '!schedule': self._schedule_event
        }

    def get_question(self):
        pass

    def correct(self, submission):
        for test_case, answer in zip(self.test_cases, self.answers):
            if self.run(submission, test_case) == answer:
                continue
            else:
                return False
        return True

    def run(self, func, *args):
        module_code = textwrap.dedent(func)
        dynmodule.load(module_code)  # defines module's contents
        return dynmodule.func(*args)

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
            await self.client.delete_message(message)
            msg = 'Thank you for your submission, {0.author.display_name}.'.format(message)
            return
            # await self.client.send_message(message.channel, msg)

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
        print(msg_args)
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
                lang = msg_args[1].lower()
                if lang not in self.supported_langs:
                    await self.client.send_message(message.channel,
                                                   "`{}` is not a supported language.".format(lang))
                    return
            print(self.round_time(sked_time), lang)

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
