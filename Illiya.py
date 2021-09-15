import discord
from discord.ext import commands, tasks
import itertools
from youtube_dl import YoutubeDL
import random
import giphy_client
from giphy_client.rest import ApiException
import TenGiphPy
import os
import asyncio
from discordTogether import DiscordTogether

from async_timeout import timeout
from functools import partial


bot = commands.Bot(command_prefix = ('Иллия, ', 'Иллия ', 'иллия ', 'иллия, ','Иля, ', 'Иля ', 'иля, ', 'иля '))
togetherControl = DiscordTogether(bot)
api_instance = giphy_client.DefaultApi()

giphy_token = os.environ.get('G_TOKEN')
token = os.environ.get('BOT_TOKEN')
t_token = os.environ.get('T_TOKEN')
t = TenGiphPy.Tenor(token=t_token)

bot.remove_command('help')

FFMPEG_PATH = '/home/runner/Illiya/node_modules/ffmpeg-static/ffmpeg'


status = itertools.cycle(['братике', 'дырочке', 'коробке', 'сестричке', 'твоей попке'])

#-----------------------------------------------------------------------------------------------

ytdlopts =  {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp4',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
    }

ffmpegopts = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

ytdl = YoutubeDL(ytdlopts)


class VoiceConnectionError(commands.CommandError):
    """Custom Exception class for connection errors."""


class InvalidVoiceChannel(VoiceConnectionError):
    """Exception for cases of invalid Voice Channels."""


class YTDLSource(discord.PCMVolumeTransformer):

    def __init__(self, source, *, data, requester):
        super().__init__(source)
        self.requester = requester

        self.title = data.get('title')
        self.web_url = data.get('webpage_url')

    def __getitem__(self, item: str):
        """Allows us to access attributes similar to a dict.
        This is only useful when you are NOT downloading.
        """
        return self.__getattribute__(item)

    @classmethod
    async def create_source(cls, ctx, search: str, *, loop, download=False):
        loop = loop or asyncio.get_event_loop()

        to_run = partial(ytdl.extract_info, url=search, download=download)
        data = await loop.run_in_executor(None, to_run)

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        await ctx.send(f'```ini\n[Добавила {data["title"]} в очередь.]\n```')

        if download:
            source = ytdl.prepare_filename(data)
        else:
            return {'webpage_url': data['webpage_url'], 'requester': ctx.author, 'title': data['title']}

        return cls(discord.FFmpegPCMAudio(source, ** ffmpegopts), data=data, requester=ctx.author)

    @classmethod
    async def regather_stream(cls, data, *, loop):
        """Used for preparing a stream, instead of downloading.
        Since Youtube Streaming links expire."""
        loop = loop or asyncio.get_event_loop()
        requester = data['requester']

        to_run = partial(ytdl.extract_info, url=data['webpage_url'], download=False)
        data = await loop.run_in_executor(None, to_run)

        return cls(discord.FFmpegPCMAudio(data['url'], ** ffmpegopts), data=data, requester=requester)

#-------------------------------------

class MusicPlayer(commands.Cog):
    """A class which is assigned to each guild using the bot for Music.
    This class implements a queue and loop, which allows for different guilds to listen to different playlists
    simultaneously.
    When the bot disconnects from the Voice it's instance will be destroyed.
    """

    __slots__ = ('bot', '_guild', '_channel', '_cog', 'queue', 'next', 'current', 'np', 'volume', 'gf')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.np = None  # Now playing message
        self.volume = .5
        self.current = None

        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        """Our main player loop."""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next.clear()

            try:
                # Wait for the next song. If we timeout cancel the player and disconnect...
                async with timeout(300):  # 5 minutes...
                    source = await self.queue.get()
            except asyncio.TimeoutError:
                return self.destroy(self._guild)

            if not isinstance(source, YTDLSource):
                # Source was probably a stream (not downloaded)
                # So we should regather to prevent stream expiration
                try:
                    source = await YTDLSource.regather_stream(source, loop=self.bot.loop)
                except Exception as e:
                    await self._channel.send(f'Братик, ошибка при воспроизведении.\n'
                                             f'```css\n[{e}]\n```')
                    continue

            source.volume = self.volume
            self.current = source

            self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
            self.np = await self._channel.send(f'**Сейчас играет:** `{source.title}` по просьбе '
                                               f'`{source.requester}`')
            self.gf = await self._channel.send('https://tenor.com/view/anime-dance-moves-grooving-finger-wag-gif-17295058')
            await self.next.wait()
            await self.next.wait()

            # Make sure the FFmpeg process is cleaned up.
            source.cleanup()
            self.current = None

            try:
                # We are no longer playing this song...
                await self.np.delete()
                await self.gf.delete()
            except discord.HTTPException:
                pass

    def destroy(self, guild):
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self._cog.cleanup(guild))


#-------------------------------------

class Music(commands.Cog):
    """Music related commands."""

    __slots__ = ('bot', 'players')

    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            del self.players[guild.id]
        except KeyError:
            pass

    async def __local_check(self, ctx):
        """A local check which applies to all commands in this cog."""
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    async def __error(self, ctx, error):
        """A local error handler for all errors arising from commands in this cog."""
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.send('This command can not be used in Private Messages.')
            except discord.HTTPException:
                pass
        elif isinstance(error, InvalidVoiceChannel):
            await ctx.send('А ты точно в нужном канале, братик?')


    def get_player(self, ctx):
        """Retrieve the guild player, or generate one."""
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx)
            self.players[ctx.guild.id] = player

        return player

    @commands.command(name='зайди', aliases=['join'])
    async def connect_(self, ctx):
        try:
            channel = ctx.author.voice.channel
        except:
            await ctx.send('Бра~тик, я не могу войти T~T')

        vc = ctx.voice_client

        if vc:
            if vc.channel.id == channel.id:
                return
            try:
                await vc.move_to(channel)
            except asyncio.TimeoutError:
                await ctx.send(f'Хотела зайти в : <{channel}>, но устала ждать.')
        else:
            try:
                await channel.connect()
            except asyncio.TimeoutError:
                await ctx.send(f'Хотела зайти в : <{channel}>, но устала ждать.')

        await ctx.send(f'Подключилась к : **{channel}**', delete_after=20)

    @commands.command(name='музыку', aliases=['music'])
    async def play_(self, ctx, *, search: str):
        await ctx.trigger_typing()

        vc = ctx.voice_client

        if not vc:
            await ctx.invoke(self.connect_)

        player = self.get_player(ctx)
        source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop, download=False)

        await player.queue.put(source)

    @commands.command(name='пауза')
    async def pause_(self, ctx):
        """Pause the currently playing song."""
        vc = ctx.voice_client

        if not vc or not vc.is_playing():
            return await ctx.send('Я ничего не включала!')
        elif vc.is_paused():
            return

        vc.pause()
        await ctx.send(f'**`{ctx.author}`**: Поставил на паузу (Бейте его)!')

    @commands.command(name='продолжить')
    async def resume_(self, ctx):
        """Resume the currently paused song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('Я ничего не включала!', )
        elif not vc.is_paused():
            return

        vc.resume()
        await ctx.send(f'**`{ctx.author}`**: Вернул музыку на родину. Ура!')

    @commands.command(name='скип')
    async def skip_(self, ctx):
        """Skip the song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('Я ничего не включала!')

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return

        vc.stop()
        await ctx.send(f'**`{ctx.author}`**: Пропускает песню!')

    @commands.command(name='очередь', aliases=['q', 'playlist'])
    async def queue_info(self, ctx):
        """Retrieve a basic queue of upcoming songs."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('Я ничего не включала!')

        player = self.get_player(ctx)
        if player.queue.empty():
            return await ctx.send('А мне играть то и нечего...')
        upcoming = list(itertools.islice(player.queue._queue, 0, 5))

        fmt = '\n'.join(f'**`{_["title"]}`**' for _ in upcoming)
        embed = discord.Embed(title=f'А скоро будет - Следующие {len(upcoming)}', description=fmt)

        await ctx.send(embed=embed)

    @commands.command(name='играет', aliases=['np', 'current', 'currentsong', 'playing'])
    async def now_playing_(self, ctx):
        """Display information about the currently playing song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('ВЕРНИ В ЧАТ, БРАТИК!!!!', )

        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send('Я ничего не включала!')

        try:
            await player.np.delete()
        except discord.HTTPException:
            pass

        player.np = await ctx.send(f'**Сейчас играть:** `{vc.source.title}` '
                                   f'по запросу `{vc.source.requester}`')

    @commands.command(name='звук', aliases=['vol'])
    async def change_volume(self, ctx, *, vol: float):
        """Change the player volume.
        Parameters
        ------------
        volume: float or int [Required]
            The volume to set the player to in percentage. This must be between 1 and 100.
        """
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('ВЕРНИ В ЧАТ, БРАТИК!!!!', )

        if not 0 < vol < 101:
            return await ctx.send('Сколько из 100 бананов тебе дать?))')

        player = self.get_player(ctx)

        if vc.source:
            vc.source.volume = vol / 100

        player.volume = vol / 100
        await ctx.send(f'**`{ctx.author}`**: Поставила бананы на **{vol}%**')

    @commands.command(name='стоп', aliases=['leave'])
    async def stop_(self, ctx):
        """Stop the currently playing song and destroy the player.
        !Warning!
            This will destroy the player assigned to your guild, also deleting any queued songs and settings.
        """
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('Я ничего не включала!')

        await self.cleanup(ctx.guild)
		
#-------------------------------------

class Other(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		
	@commands.command()
	async def они(self, ctx):
		await ctx.send('Чан!')
	
	@commands.command()
	async def привет(self, ctx):
		author = ctx.message.author
		await ctx.send(f'Братик, {ctx.author.name}, привет! Чем сегодня займемся?')
		await ctx.send('https://tenor.com/view/anime-fate-illya-cute-sleepy-gif-12866140')
		
	@commands.command()
	async def предскажи(self, ctx, *, qs):
		"""Магический шар"""
		res = ['Да!', 'Нет!', 'Возможно', 'Не думаю', 
					'Лучше этого не делать', 'Конечно!', 'Я не знаю',
					'Не сегодня', 'Попробуй завтра', 'Лучше займись другим делом',
					'Попробуй еще', 'Сделай это прямо сейчас!', 'Я уверена, братик, все получится!',
					'И не мечтай']
		await ctx.send(f'Ты спросил(а): \"{qs}\"\n{random.choice(res)}')
		
	@commands.command()
	async def число(self, ctx, *num):
		"""Случайное число"""
		if 'от' in num:
			await ctx.send(random.randrange((int(num[1])),int(num[3]) + 1))
		else:
			await ctx.send(random.randrange(int(num[1]) + 1))
			
	@commands.command()
	async def помощь(self, ctx, *cog):
		"""Узнать комманды Иллии"""
		
		embed = discord.Embed(title = 'Вот что я могу, братик!', color =  discord.Color.red())
		embed.add_field(name = 'Команда: музыку', value = 'Включает музыку по ссылке youtube.. (Пример: Иля музыку \"ссылка на видео\")')
		embed.add_field(name = 'Команда: стоп', value = 'Остановить проигрывание музыки.. (Пример: Иля стоп)')
		embed.add_field(name = 'Команда: зайди', value = 'Подключение к серверу.. (Пример: Иля зайди)')
		embed.add_field(name = 'Команда: очередь', value = 'Посмотреть музыкальную очередь.. (Пример: Иля очередь)')
		embed.add_field(name = 'Команда: пауза', value = 'Поставить музыку на паузу.. (Пример: Иля пауза)')
		embed.add_field(name = 'Команда: продолжить', value = 'Продолжить проигрывание музыки.. (Пример: Иля продолжить)')
		embed.add_field(name = 'Команда: скип', value = 'Включить следующую песню в очереди (Пример: Иля скип)')
		embed.add_field(name = 'Команда: играет', value = 'Узнать какой трэк играет.. (Пример: Иля играет	)')
		
		
		embed.add_field(name = 'Команда: они', value = 'Чан! (Пример: Иля они)')
		embed.add_field(name = 'Команда: привет', value = 'Поприветствуй бота.. (Пример: Иллия привет )')
		embed.add_field(name = 'Команда: предскажи', value = 'Магический шар предсказаний.. (Пример: Иля предскажи идти ли мне спать? )')
		embed.add_field(name = 'Команда: число', value = 'Случайное число.. (Пример: Иля число от 1 до 10, Иля число до 5 )')
		embed.add_field(name = 'Команда: помощь', value = 'Вызвать меню помощи (Пример: Иля помощь)')
		embed.add_field(name = 'Команда: гг', value = 'Найти гифку с Giphy (Пример: Иля гг котик )')
		embed.add_field(name = 'Команда: тг', value = 'Найти гифку с Tenor (Пример: Иля тг котик )')
		embed.add_field(name = 'Команда: чмок', value = 'Чмокнит кого-нибудь (Пример: Иля поцелуй Ваню)')
		embed.add_field(name = 'Команда: кусь', value = 'Кусить кого-нибудь (Пример: Иля кусь Ваню)')
		embed.add_field(name = 'Команда: поцеловать', value = 'Поцеловать кого-нибудь (Пример: Иля поцеловать Ваню)')
		
		await ctx.send(embed = embed)
		
	@commands.command()
	async def чмок(self, ctx, part):
		await ctx.send(f'Чмок {part}')
		await ctx.send('https://tenor.com/view/loliloliloli-sexy-red-hair-gif-14649359')
		
	@commands.command()
	async def кусь(self, ctx, part):
		await ctx.send(f'Кусь {part}')
		await ctx.send('https://tenor.com/view/bite-anime-gif-8259627')
		
	@commands.command()
	async def поцеловать(self, ctx, part):
		await ctx.send(f'{ctx.author.name} целует {part}, как мило :3')
		await ctx.send('https://tenor.com/view/anime-kiss-tongue-drool-passionate-gif-13516822')
		
	@commands.command()
	async def иди(self, ctx, *, part):
		if 'на' in part:
			await ctx.send(f'{ctx.author.name} иди ты сам туда!')
			
	@commands.command()
	async def пошла(self, ctx, *, part):
		if 'на' in part:
			await ctx.send(f'{ctx.author.name} иди ты сам туда!')

	@commands.command()
	async def полезность(self, ctx, *, part):
		await ctx.channel.purge(limit=1)
		embed = discord.Embed(color =  discord.Color.purple())
		embed.add_field(name = (f'Полезность от {ctx.author.name}!'), value = part)
		await ctx.send(embed = embed)


	@commands.command()
	async def рыбалочка(self, ctx):
		link = await togetherControl.create_link(ctx.author.voice.channel.id, 'fishing')
		await ctx.send(f"Достаю удочки! Идем рыбачить с братиком!\n{link}")

#-------------------------------------
async def search_gifs(query):
	try:
		response = api_instance.gifs_search_get(str(giphy_token), query, rating='g')
		st = list(response.data)
		gif = random.choices(st)

		return gif[0].url

	except ApiException as e:
		return "Exception when calling DefaultApi->gifs_search_get: %s\n" % e
		
class Search(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@commands.command()
	async def гг(self, ctx, *search):
		"""Ищет рандомную гиф с Giphy"""
		author = ctx.message.author
		try:
			gif = await search_gifs(str(search))
			await ctx.send(f'Смотри что я нашла, братик {author.mention}: ' + gif)
		except:
			await ctx.send(f'Прости, братик {author.mention}, я не смогла ничего найти')
	@commands.command()
	async def тг(self, ctx, *giftag):
		"""Ищет рандомную гиф с Тенора"""
		author = ctx.message.author
		try:
			getgifurl = t.random(str(giftag))
			await ctx.send(f'Смотри что я нашла, братик {author.mention}: ')
			await ctx.send(f'{getgifurl}')
		except:
			await ctx.send(f'Прости, братик {author.mention}, я не смогла ничего найти')

#-------------------------------------
@bot.event
async def on_ready():
	change_status.start()
	print('Бот запущен')
			
@bot.event
async def on_command_error(ctx, error):
	if isinstance(error, commands.MissingPermissions):
		await ctx.send('Плохой братик! Тебе нельзя такое делать!')
	elif isinstance(error, commands.MissingRequiredArgument):
		await ctx.send('Чего-то не хватает, братик...')


@tasks.loop(seconds = 10)
async def change_status():
	await bot.change_presence(activity = discord.Game(next(status)))

#-------------------------------------



bot.add_cog(Search(bot))
bot.add_cog(Other(bot))
bot.add_cog(Music(bot))
bot.run(str(token)) 
