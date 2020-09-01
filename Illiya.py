import discord
from discord.ext import commands, tasks
from itertools import cycle
import youtube_dl
from discord.utils import get
import random
import giphy_client
from giphy_client.rest import ApiException
import tenorpy
import os

bot = commands.Bot(command_prefix = ('Иллия, ', 'Иллия ', 'иллия ', 'иллия, ','Иля, ', 'Иля ', 'иля, ', 'иля '))
api_instance = giphy_client.DefaultApi()
giphy_token = os.environ.get('G_TOKEN')
token = os.environ.get('BOT_TOKEN')
t = tenorpy.Tenor()

bot.remove_command('help')

status = cycle(['братике', 'дырочке', 'коробке', 'сестричке', 'твоей попке'])

#-------------------------------------
youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
	def __init__(self, source, *, data, volume=0.5):
		super().__init__(source, volume)
		self.data = data
		self.title = data.get('title')
		self.url = data.get('url')
		
	@classmethod
	async def from_url(cls, url, *, loop=None, stream=False):
		loop = loop or asyncio.get_event_loop()
		data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
		
		if 'entries' in data:
			data = data['entries'][0]
		
		filename = data['url'] if stream else ytdl.prepare_filename(data)
		return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
		
class Music(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
	
	@commands.command()
	async def стоп(self, ctx):
		'''Остановить проигрывание музыки'''
		await ctx.voice_client.disconnect()
		
	@commands.command()
	async def музыку(self, ctx, *, url):
		'''Проигрывает музыку с ютуба.'''
		async with ctx.typing():
			player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
			ctx.voice_client.play(player, after=lambda e: print('Упс, ошибка плеера: %s' % e) if e else None)
		await ctx.send('Включила: {}'.format(player.title))
		await ctx.send('https://tenor.com/view/anime-dance-moves-grooving-finger-wag-gif-17295058')
		
	@музыку.before_invoke
	async def ensure_voice(self, ctx):
		if ctx.voice_client is None:
			if ctx.author.voice:
				await ctx.author.voice.channel.connect()
			else:
				await ctx.send("Что-то не так")
				raise commands.CommandError("Братик, тебя нет на сервере.")
		elif ctx.voice_client.is_playing():
			ctx.voice_client.stop()
			
	@commands.command()
	async def ЫБОШ(self, ctx):
		'''АРМАНЕН'''
		await ctx.author.voice.channel.connect()
		url = 'https://www.youtube.com/watch?v=txHKylslfrE'
		player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
		ctx.voice_client.play(player, after=lambda e: print('Упс, ошибка плеера: %s' % e) if e else None)
		await ctx.send('АРМАНЕН!')
		await ctx.send('https://tenor.com/view/ilya-illya-prisma-ilya-prisma-illya-fate-gif-13254265')
		
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
		embed.add_field(name = 'Команда: ЫБОШ', value = 'АРМАНЕН! (Пример: Иля ЫБОШ)')
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
	if isinstance(error, commands.MissingRequiredArgument):
		await ctx.send('Я не понимаю, ты что-то забыл дописать')
		await ctx.send('https://tenor.com/view/anime-fate-illya-cute-funny-gif-12866145')
		
@bot.event
async def on_command_error(ctx, error):
	if isinstance(error, commands.CommandNotFound):
		await ctx.send('https://tenor.com/view/illya-blink-anime-eyes-cute-gif-16059710')

@tasks.loop(seconds = 10)
async def change_status():
	await bot.change_presence(activity = discord.Game(next(status)))

#-------------------------------------

bot.add_cog(Search(bot))
bot.add_cog(Other(bot))
bot.add_cog(Music(bot))
bot.run(str(token)) 

