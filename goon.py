import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio

# Function to read the bot token from secret.secret
def read_token():
    with open("secret.secret", "r") as file:
        return file.read().strip()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Suppress noise about console usage from youtube_dl
youtube_dl.utils.bug_reports_message = lambda: ''

# YouTube DL options
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
    'default_search': 'auto',  # Treat input as a search query if it's not a URL
    'source_address': '0.0.0.0',  # Bind to IPv4
    'extract_flat': True,  # Avoid extracting unnecessary metadata
    'prefer_ffmpeg': True,  # Prefer FFmpeg for audio extraction
}

# FFmpeg options with audio normalization
ffmpeg_options = {
    'options': '-vn -b:a 192k -af loudnorm'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

# Queue system
queue = []

# YouTube DL extractor
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

# Function to play the next song in the queue
async def play_next(ctx):
    if len(queue) > 0:
        query = queue.pop(0)
        player = await YTDLSource.from_url(query, loop=bot.loop, stream=True)
        ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))
        await ctx.send(f'Now playing: {player.title}')
    else:
        await ctx.send("The queue is empty. Add more songs with `!goon <query>`.")

# Create a command group for GoonBot
@bot.group(name="goon", invoke_without_command=True)
async def goon(ctx, *, query: str = None):
    if query is None:
        await ctx.send("Please provide a search query. Usage: `!goon <query>`")
        return

    # Join the voice channel if not already connected
    if not ctx.message.author.voice:
        await ctx.send(f"{ctx.message.author.name} is not connected to a voice channel")
        return

    voice_client = ctx.message.guild.voice_client
    if not voice_client or not voice_client.is_connected():
        channel = ctx.message.author.voice.channel
        voice_client = await channel.connect()

    # Add the song to the queue
    queue.append(query)
    await ctx.send(f"Added to queue: {query}")

    # If nothing is playing, start playing the song
    if not voice_client.is_playing():
        await play_next(ctx)

# Command: !goon queue
@goon.command(name="queue", help="Displays the current queue")
async def show_queue(ctx):
    if len(queue) == 0:
        await ctx.send("The queue is empty.")
    else:
        queue_list = "\n".join([f"{i+1}. {song}" for i, song in enumerate(queue)])
        await ctx.send(f"Current queue:\n{queue_list}")

# Command: !goon skip
@goon.command(name="skip", help="Skips the current song")
async def skip(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
        await ctx.send("Skipped the current song.")
    else:
        await ctx.send("No audio is playing.")

# Command: !goon leave
@goon.command(name="leave", help="Leaves the voice channel")
async def leave(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_connected():
        await voice_client.disconnect()
        queue.clear()  # Clear the queue when the bot leaves
    else:
        await ctx.send("The bot is not connected to a voice channel.")

# Command: !goon pause
@goon.command(name="pause", help="Pauses the current song")
async def pause(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.pause()
    else:
        await ctx.send("No audio is playing.")

# Command: !goon resume
@goon.command(name="resume", help="Resumes the paused song")
async def resume(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_paused():
        voice_client.resume()
    else:
        await ctx.send("The audio is not paused.")

# Command: !goon stop
@goon.command(name="stop", help="Stops the current song")
async def stop(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
        queue.clear()  # Clear the queue when the bot stops
    else:
        await ctx.send("No audio is playing.")

# Run the bot
bot.run(read_token())
