from discord.ext import commands
import discord
import asyncio
import youtube_dl
import logging
import math
import time
import youtube_dl as ytdl

max_volume = 250
vote_skip = True
vote_skip_ratio = 0.5

YTDL_OPTS = {
    "default_search": "ytsearch",
    "format": "bestaudio/best",
    "quiet": True,
    "extract_flat": "in_playlist"
}


class Video:
    """Class containing information about a particular video."""

    def __init__(self, url_or_search, requested_by):
        """Plays audio from (or searches for) a URL."""
        with ytdl.YoutubeDL(YTDL_OPTS) as ydl:
            video = self._get_info(url_or_search)
            video_format = video["formats"][0]
            self.stream_url = video_format["url"]
            self.video_url = video["webpage_url"]
            self.title = video["title"]
            self.uploader = video["uploader"] if "uploader" in video else ""
            self.thumbnail = video[
                "thumbnail"] if "thumbnail" in video else None
            self.requested_by = requested_by

    def _get_info(self, video_url):
        with ytdl.YoutubeDL(YTDL_OPTS) as ydl:
            info = ydl.extract_info(video_url, download=False)
            video = None
            if "_type" in info and info["_type"] == "playlist":
                return self._get_info(
                    info["entries"][0]["url"])  # get info for first video
            else:
                video = info
            return video

    def get_embed(self):
        """嵌入此視頻的信息"""
        embed = discord.Embed(
            title=self.title, descolcription=self.uploader, url=self.video_url,color=0xffffff)
        embed.set_footer(
            text=f"由 {self.requested_by.name} 播放",
            icon_url=self.requested_by.avatar_url)
        if self.thumbnail:
            embed.set_thumbnail(url=self.thumbnail)
        return embed

# TODO: abstract FFMPEG options into their own file?
FFMPEG_BEFORE_OPTS = '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
"""
Command line options to pass to `ffmpeg` before the `-i`.

See https://stackoverflow.com/questions/43218292/youtubedl-read-error-with-discord-py/44490434#44490434 for more information.
Also, https://ffmpeg.org/ffmpeg-protocols.html for command line option reference.
"""


async def audio_playing(ctx):
    """在繼續之前檢查音頻當前是否正在播放"""
    client = ctx.guild.voice_client
    if client and client.channel and client.source:
        return True
    else:
        return


async def in_voice_channel(ctx):
    """檢查命令發送者是否與機器人在同一語音通道中"""
    voice = ctx.author.voice
    bot_voice = ctx.guild.voice_client
    if voice and bot_voice and voice.channel and bot_voice.channel and voice.channel == bot_voice.channel:
        return True
    else:
        return


async def is_audio_requester(ctx):
    """檢查命令發送者是否是歌曲請求者"""
    music = ctx.bot.get_cog("Music")
    state = music.get_state(ctx.guild)
    permissions = ctx.channel.permissions_for(ctx.author)
    if permissions.administrator or state.is_requester(ctx.author):
        return True
    else:
        return


class Music(commands.Cog):
    """🎵"""

    def __init__(self, bot):
        self.bot = bot
        self.states = {}
        self.bot.add_listener(self.on_reaction_add, "on_reaction_add")

    def get_state(self, guild):
        if guild.id in self.states:
            return self.states[guild.id]
        else:
            self.states[guild.id] = GuildState()
            return self.states[guild.id]

    @commands.command(aliases=["resume"])
    @commands.guild_only()
    @commands.check(audio_playing)
    @commands.check(in_voice_channel)
    @commands.check(is_audio_requester)
    async def pause(self, ctx):
        """暫停/撥放音樂"""
        client = ctx.guild.voice_client
        self._pause_audio(client)

    def _pause_audio(self, client):
        if client.is_paused():
            client.resume()
        else:
            client.pause()

    @commands.command(aliases=["vol", "v"])
    @commands.guild_only()
    @commands.check(audio_playing)
    @commands.check(in_voice_channel)
    @commands.check(is_audio_requester)
    async def volume(self, ctx, volume: int):
        """改變音量(0~250)"""
        state = self.get_state(ctx.guild)

        # make sure volume is nonnegative
        if volume < 0:
            volume = 0

        max_vol = max_volume
        if max_vol > -1:  # check if max volume is set
            # clamp volume to [0, max_vol]
            if volume > max_vol:
                volume = max_vol

        client = ctx.guild.voice_client

        state.volume = float(volume) / 100.0
        client.source.volume = state.volume  # update the AudioSource's volume to match

    @commands.command()
    @commands.guild_only()
    @commands.check(audio_playing)
    @commands.check(in_voice_channel)
    async def skip(self, ctx):
        """跳過"""
        state = self.get_state(ctx.guild)
        client = ctx.guild.voice_client
        if ctx.channel.permissions_for(
                ctx.author).administrator or state.is_requester(ctx.author):
            # immediately skip if requester or admin
            client.stop()
        elif vote_skip:
            # vote to skip song
            channel = client.channel
            self._vote_skip(channel, ctx.author)
            # announce vote
            users_in_channel = len([
                member for member in channel.members if not member.bot
            ])  # don't count bots
            required_votes = math.ceil(
                vote_skip_ratio * users_in_channel)
            await ctx.send(
                f"{ctx.author.mention} 投票跳過 ({len(state.skip_votes)}/{required_votes} 個)"
            )
        else:
            await ctx.send("跳過投票被禁用")

    def _vote_skip(self, channel, member):
        """投票以跳過正在播放的歌曲"""
        logging.info(f"{member.name} 投票跳過")
        state = self.get_state(channel.guild)
        state.skip_votes.add(member)
        users_in_channel = len([
            member for member in channel.members if not member.bot
        ])  # don't count bots
        if (float(len(state.skip_votes)) /
                users_in_channel) >= vote_skip_ratio:
            # enough members have voted to skip, so skip the song
            logging.info(f"足夠的票，跳過...")
            channel.guild.voice_client.stop()

    def _play_song(self, client, state, song):
        state.now_playing = song
        state.skip_votes = set()  # clear skip votes
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(song.stream_url, before_options=FFMPEG_BEFORE_OPTS), volume=state.volume)

        def after_playing(err):
            if len(state.playlist) > 0:
                next_song = state.playlist.pop(0)
                self._play_song(client, state, next_song)
            else:
                asyncio.run_coroutine_threadsafe(client.disconnect(),
                                                 self.bot.loop)

        client.play(source, after=after_playing)

    @commands.command(aliases=["np"])
    @commands.guild_only()
    @commands.check(audio_playing)
    async def nowplaying(self, ctx):
        """顯示有關當前歌曲的信息"""
        state = self.get_state(ctx.guild)
        message = await ctx.send("", embed=state.now_playing.get_embed())
        await self._add_reaction_controls(message)

    @commands.command(aliases=["q", "playlist"])
    @commands.guild_only()
    @commands.check(audio_playing)
    async def queue(self, ctx):
        """顯示當前播放隊列。"""
        state = self.get_state(ctx.guild)
        await ctx.send(self._queue_text(state.playlist))

    def _queue_text(self, queue):
        """返回描述給定歌曲隊列的文本塊。"""
        if len(queue) > 0:
            message = [f"有 **{len(queue)}** 首歌在播放隊列:"]
            message += [
                f"  {index+1}. **{song.title}** (由 **{song.requested_by.name}** 撥放)"
                for (index, song) in enumerate(queue)
            ]  # add individual songs
            return "\n".join(message)
        else:
            return "播放隊列為空。"

    @commands.command(aliases=["cq"])
    @commands.guild_only()
    @commands.check(audio_playing)
    @commands.has_permissions(administrator=True)
    async def clearqueue(self, ctx):
        """在不離開頻道的情況下清除播放隊列。"""
        state = self.get_state(ctx.guild)
        state.playlist = []
        await ctx.send("完成")

    @commands.command(aliases=["jq"])
    @commands.guild_only()
    @commands.check(audio_playing)
    @commands.has_permissions(administrator=True)
    async def jumpqueue(self, ctx, song: int, new_index: int):
        """將索引處的歌曲移動到隊列中的“new_index”"""
        state = self.get_state(ctx.guild)  # get state for this guild
        if 1 <= song <= len(state.playlist) and 1 <= new_index:
            song = state.playlist.pop(song - 1)  # take song at index...
            state.playlist.insert(new_index - 1, song)  # and insert it.

            await ctx.send(self._queue_text(state.playlist))
        else:
            await ctx.send("You must use a valid index.")

    @commands.command(aliases=["p"])
    @commands.guild_only()
    async def play(self, ctx, *, url):
        """播放"""

        message = await ctx.send("即將播放請等待")

        client = ctx.guild.voice_client
        state = self.get_state(ctx.guild)  # get the guild's state

        

        if client and client.channel:
            try:
                video = Video(url, ctx.author)
            except youtube_dl.DownloadError as e:
                await ctx.send(f"下載時出錯: {e}")
                return
            state.playlist.append(video)
            await ctx.send(
                "添加到隊列", embed=video.get_embed())
            await message.delete()
        else:
            if ctx.author.voice is not None and ctx.author.voice.channel is not None:
                channel = ctx.author.voice.channel
                try:
                    video = Video(url, ctx.author)
                except youtube_dl.DownloadError as e:
                    await ctx.send(
                        f"下載時出錯 {e}")
                    return
                client = await channel.connect()
                self._play_song(client, state, video)
                await message.delete()
                message = await ctx.send(embed=video.get_embed())
                await self._add_reaction_controls(message)
                logging.info(f"正在播放 '{video.title}'")
            else:
                await message.delete()
                await ctx.send(
                    "請先加入語音頻道")

            
        await ctx.send(embed=embed)
            
    async def on_reaction_add(self, reaction, user):
        """Respods to reactions added to the bot's messages, allowing reactions to control playback."""
        message = reaction.message
        CONTROLS = ["⏮", "⏯", "⏭", "🔉", "🔊", "❌"]
        if user != self.bot.user and message.author == self.bot.user:
            await message.remove_reaction(reaction, user)
            if message.guild and message.guild.voice_client:
                user_in_channel = user.voice and user.voice.channel and user.voice.channel == message.guild.voice_client.channel
                permissions = message.channel.permissions_for(user)
                guild = message.guild
                state = self.get_state(guild)
                if permissions.administrator or (
                        user_in_channel and state.is_requester(user)):
                    client = message.guild.voice_client
                    if reaction.emoji == "⏯":
                        # pause audio
                        self._pause_audio(client)
                    elif reaction.emoji == "⏭":
                        # skip audio
                        client.stop()
                        time.sleep(1)

                        state = self.get_state(message.guild)
                        msg = await message.channel.send("", embed=state.now_playing.get_embed())
                        await self._add_reaction_controls(msg)
                        for control in CONTROLS:
                          await message.remove_reaction(control, self.bot.user)
                    elif reaction.emoji == "⏮":
                        state.playlist.insert(
                            0, state.now_playing
                        )  # insert current song at beginning of playlist
                        client.stop()  # skip ahead
                    elif reaction.emoji == "🔉":
                        state = self.get_state(message.guild)
                        volume = client.source.volume*100
                        volume -= 20
                        if volume < -1:
                                volume = 0
                        client = message.guild.voice_client
                        state.volume = float(volume) / 100.0
                        client.source.volume = state.volume 
                    elif reaction.emoji == "🔊":
                        state = self.get_state(message.guild)
                        volume = client.source.volume*100
                        volume += 20
                        if volume > max_volume:
                                volume = max_volume
                        client = message.guild.voice_client
                        state.volume = float(volume) / 100.0
                        client.source.volume = state.volume 
                    elif reaction.emoji == "❌":
                        client = message.guild.voice_client
                        state = self.get_state(message.guild)
                        if client and client.channel:
                          await client.disconnect()
                          state.playlist = []
                          state.now_playing = None
                          for control in CONTROLS:
                            await message.remove_reaction(control, self.bot.user)

                elif reaction.emoji == "⏭" and vote_skip and user_in_channel and message.guild.voice_client and message.guild.voice_client.channel:
                    # ensure that skip was pressed, that vote skipping is
                    # enabled, the user is in the channel, and that the bot is
                    # in a voice channel
                    voice_channel = message.guild.voice_client.channel
                    self._vote_skip(voice_channel, user)
                    # announce vote
                    channel = message.channel
                    users_in_channel = len([
                        member for member in voice_channel.members
                        if not member.bot
                    ])  # don't count bots
                    required_votes = math.ceil(
                        vote_skip_ratio * users_in_channel)
                    await channel.send(
                        f"{user.mention} voted to skip ({len(state.skip_votes)}/{required_votes} votes)"
                    )

    async def _add_reaction_controls(self, message):
        """Adds a 'control-panel' of reactions to a message that can be used to control the bot."""
        CONTROLS = ["⏮", "⏯", "⏭", "🔉", "🔊", "❌"]
        for control in CONTROLS:
            await message.add_reaction(control)

def setup(bot):
    bot.add_cog(Music(bot))


class GuildState:
    """Helper class managing per-guild state."""

    def __init__(self):
        self.volume = 100
        self.playlist = []
        self.skip_votes = set()
        self.now_playing = None

    def is_requester(self, user):
        try:
          return self.now_playing.requested_by == user
        except:
          return