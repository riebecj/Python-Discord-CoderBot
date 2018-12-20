from datetime import datetime, timedelta
import logging.config
import dynmodule
import textwrap  
import dateparser
import random
import asyncio
import discord
import operator
import traceback


log = logging.getLogger(__name__)
loop = asyncio.get_event_loop()


class Bot(object):
    def __init__(self):
        # token for Discord API (VERY SECRET)
        self.token = 'TOKEN_STRING'
        # prefix for all commands to bot
        self.prefix = '!'
        # specific channel lock. Won't reply or post to any other public channel
        self.channel_lock = 'proving-grounds'
        # sets the client 
        self.client = discord.Client(loop=loop)
        # dictionary for commands
        self.commands = dict()
        # list of supported Languages
        self.supported_langs = None
        # adds the event handler for messages
        self.client.event(self.on_message)
        # get bot start time
        self._start_time = datetime.now()
        # dict for holding leaderboard
        self.alltime_leaders = {}
        # dict for holding challenge scores
        self.challenge_participants = {}
        # database of pointers to language specific questions
        self.database = None
        # Bool to detect ongoing challenge
        self.ongoing = False
        # Title of challenge problem
        self.title = None
        # Challenge problem
        self.question = None
        # list of test cases
        self.test_cases = None
        # list of answers for each test case
        self.answers = None
        # int of seconds left for the challenge (used in computing score)
        self.challenge_time = 0
        # total time of challenge (int of seconds used in computing score)
        self.total_time = 0
        # Total points for the question 
        self.points = 0
        # current challenge language
        self.lang = None
        # set the bot commands
        self.set_commands()
        # get various pointers for each language supported
        self.set_database()
        # read in the all time leaderboard 
        self.get_leaderboard()

    def get_leaderboard(self):
        """Gets the leaderboard from the persistent file"""
        self.alltime_leaders = eval(open(r'leader_data/leaderboard', 'rt').read())

    def write_leaderboard(self):
        """Overwrites the leaderboard file with new values"""
        with open(r'leader_data/leaderboard', 'wt') as lb:
            lb.truncate()
            lb.write(str(self.alltime_leaders))

    def update_alltime(self):
        """Update the All Time Leaderboard (usually after a challange is complete."""
        for user, score in self.challenge_participants.items():
            if user in self.alltime_leaders.keys():
                self.alltime_leaders[user] += score
            else:
                self.alltime_leaders[user] = score
        self.write_leaderboard()

    def set_commands(self):
        """Set the bot command to the function"""
        self.commands = {
            '!help': self._help,
            '!stats': self._stats,
            '!info': self._info,
            '!hello': self._greeting,
            '!schedule': self._schedule_event,
            '!leaderboard': self._post_alltime
        }

    async def test_submission(self, message):
        """Test the user's code submission"""
        user = message.author
        submission = message.content[1:]
        for number, (test_case, answer) in enumerate(zip(self.test_cases, self.answers)):
            try:
                output = self.run(submission, test_case)
                if output == answer:  # passed test case
                    continue
                else:  # failed test case
                    if number > 2:  # only show the first 3 test cases. The rest are hidden.
                        test_case = 'hidden'
                        answer = 'hidden'
                    await self.failed(user, test_case, output, answer)  
                    return
            except:  # bad syntax 
                msg = traceback.format_exc()
                await self.client.send_message(user, msg)
                return
        await self.correct(user)

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

    def set_database(self):
        """Ger pointers to various supported language questions"""
        self.database = {
            'python': 'python-data/questions'
        }
        self.supported_langs = self.database.keys()  # sets list of supported languages

    def run(self, func, *args):
        """executes users code in specific environments for safety"""
        if self.lang.lower() == 'python':
            module_code = textwrap.dedent(func)
            dynmodule.load(module_code)  # defines module's contents
            return dynmodule.func(*args)

    def award_points(self, user):
        """Calculate user's score upon correct submission"""
        points = round((self.challenge_time / self.total_time) * self.points)
        self.challenge_participants[user] = points

    async def end_challenge(self, channel):
        """Handle ending the Challenge event"""
        self.ongoing = False
        user, points = max(self.challenge_participants.items(), key=operator.itemgetter(1))
        msg = '\nThat is the end of this Coding Challenge!\n Congratulations to {0.display_name} for ' \
              'scoring the most points with {1}!\n'.format(user, points)
        await self.client.send_message(channel, msg)

        msg = '\nResults\n----------\n'
        for user, points in reversed(sorted(self.challenge_participants.items(), key=lambda kv: kv[1])):
            msg += "`{0.display_name}` : `{1}` points\n".format(user, points)
        await self.client.send_message(channel, msg)
        self.update_alltime()
        self.write_leaderboard()
        self.challenge_participants = {}

    async def begin_challenge(self, lang, channel):
        """"Handle the beginning of the challenge event"""
        self.ongoing = True
        available = eval(open(self.database[lang.lower()], 'rt').read())
        selection = available[random.randint(0, len(available.keys()) - 1)]
        self.title = selection['title']
        self.question = selection['question']
        self.test_cases = selection['test_cases']
        self.answers = selection['answers']
        self.challenge_time = self.total_time = selection['time_limit']*60
        self.points = selection['total_points']
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
        msg7 = "5. You may either code in the Discord chat box (Hold `Shift` when pressing enter for a new " \
               "line) or use a text editor or your favorite IDE and copy/paste the code into the chat box."
        msg8 = "Now, without further ado, we begin in 5..."

        for msg in [msg, msg2, msg3, msg4, msg5, msg6, msg7, msg8]:
            await self.client.send_message(channel, msg)
            await asyncio.sleep(5)

        for i in range(4):
            await asyncio.sleep(1)
            await self.client.send_message(channel, "{}...".format(4-i))
        await self.client.send_message(channel, "\n{}\n{}".format(self.title, self.question))
        await self.challenge_timer(channel, self.challenge_time)

    async def start(self):
        """Login"""
        await self.client.login(self.token)

        try:
            await self.client.connect()
        except discord.ClientException:
            raise

    async def stop(self):
        """Exit"""
        await self.client.logout()

    async def correct(self, user):
        """Executes when user submits a correct solution"""
        self.award_points(user)
        msg = "You passed all test cases!"
        await self.client.send_message(user, msg)

    async def failed(self, user, _input, output, expected):
        """Executes when the user failed a test case"""
        msg = "I'm sorry. You're submission did not pass all test cases.\n" \
              "Input: `{}`\nExpected output: `{}`\nYour output: `{}`".format(_input, expected, output)
        await self.client.send_message(user, msg)

    async def on_message(self, message):
        """Handle messages as commands"""
        if message.author == self.client.user:  # do not respond to itself
            return
        
        # do not respond to any other channel other than the designated one
        if message.channel.name != self.channel_lock:  
            return

        # handle code submissions during challanges
        if message.content.startswith('$'):
            if self.ongoing:
                await self.client.delete_message(message)
                msg = 'Thank you for your submission, {0.author.display_name}.'.format(message)
                if message.author not in self.challenge_participants.keys():
                    await self.test_submission(message)
                else:
                    await self.client.send_message(message.author, 'You have already submitted a correct '
                                                                   'solution and cannot submit again.')
            else:
                return

        # handle standard commands
        if message.content.startswith(self.prefix):
            for command, func in self.commands.items():
                if command in message.content:
                    await func(message)
                    return

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
                self.lang = msg_args[1]
                if self.lang.lower() not in self.supported_langs:
                    await self.client.send_message(message.channel,
                                                   "`{}` is not a supported language.".format(self.lang))
                    return
            if self.round_time(sked_time, 60) == self.round_time(datetime.now(), 60):
                await self.begin_challenge(self.lang, message.channel)
                return
        self.client.loop.create_task(self.schedule_tracker(message, self.round_time(sked_time), self.lang))

    async def schedule_tracker(self, message, event_time, lang):
        """background task to keep track of scheduled event and send reminders"""
        if 'BotModerator' not in [role.name for role in message.author.roles]:
            return
        idioms = ['Be there or be square!', 'Show up or shut up (respectfully)!', "Don't miss the boat!",
                  "You can't win if you don't play!", 'You snooze, you lose!']
        await self.client.wait_until_ready()
        channel = message.channel
        idiom = idioms[random.randint(0, len(idioms)-1)]
        msg = 'A `{}` coding challenge has been scheduled for {} PST.\n{}'.format(lang, event_time, idiom)
        await self.client.send_message(channel, msg)
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
        """Timer for Challenge events"""
        event_time = datetime.now() + timedelta(seconds=challenge_time)
        while datetime.now() < event_time:
            if self.challenge_time % 300 == 0:
                await self.client.send_message(channel, "{} remaining in this challenge".format(event_time-datetime.now()))
            await asyncio.sleep(1)
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

    async def _post_alltime(self, message):
        """Display All Time Leader Board."""
        msg = 'ALL TIME LEADER BOARD\n----------------------\n'
        for user, score in reversed(sorted(self.alltime_leaders.items(), key=lambda kv: kv[1])):
            msg += "{0.display_name} : {1} Points".format(user, score)
        await self.client.send_message(message.channel, msg)


if __name__ == '__main__':
    bot = Bot()

    asyncio.ensure_future(bot.start())
    loop.run_forever()

    loop.close()
