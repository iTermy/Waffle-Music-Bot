import discord
from discord.ext import commands
import asyncio
from music_handler import MusicHandler
from music_queue import MusicQueue, LoopMode  # Import LoopMode here

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_handler = MusicHandler()
        self.queue = MusicQueue()
        self.current_voice_client = None
        
        # FFmpeg options for audio playback
        self.ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }

    async def _join_voice_channel(self, ctx):
        """Helper method to join voice channel"""
        if not ctx.author.voice:
            await ctx.send("❌ You need to be in a voice channel!")
            return False
            
        voice_channel = ctx.author.voice.channel
        
        if ctx.voice_client is not None:
            if ctx.voice_client.channel != voice_channel:
                await ctx.voice_client.move_to(voice_channel)
        else:
            self.current_voice_client = await voice_channel.connect()
            
        return True

    async def _play_song(self, ctx):
        """Internal method to play current song"""
        if self.queue.is_empty():
            return
            
        song = self.queue.get_current()
        if not song:
            return
            
        # Refresh URL if needed (handle expired URLs)
        try:
            if song.get('webpage_url'):
                refreshed_song = self.music_handler.get_song(song['webpage_url'])
                if refreshed_song:
                    song = refreshed_song
        except Exception as e:
            print(f"Error refreshing URL: {e}")
            
        try:
            # Create audio source and play
            audio_source = discord.FFmpegPCMAudio(song['url'], **self.ffmpeg_options)
            
            def after_playing(error):
                if error:
                    print(f"Player error: {error}")
                
                # Schedule the next song to play
                coro = self._after_song(ctx)
                fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
                try:
                    fut.result()
                except:
                    pass
                    
            ctx.voice_client.play(audio_source, after=after_playing)
            
            # Send now playing embed
            duration = song.get('duration', 0)
            mins, secs = divmod(duration, 60)
            
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"**{song['title']}**",
                color=discord.Color.blue()
            )
            embed.add_field(name="Duration", value=f"{mins}:{secs:02d}")
            if song.get('thumbnail'):
                embed.set_thumbnail(url=song['thumbnail'])
                
            await ctx.send(embed=embed)
            
        except Exception as e:
            print(f"Error playing song: {e}")
            await ctx.send("❌ Error playing song, skipping...")
            await self._after_song(ctx)

    async def _after_song(self, ctx):
        """Callback after song finishes"""
        try:
            # Move to next song
            next_song = self.queue.next()
            
            if next_song:
                await self._play_song(ctx)
            else:
                await ctx.send("🏁 Queue finished!")
        except Exception as e:
            print(f"Error in after_song: {e}")

    @commands.command(name='join')
    async def join(self, ctx):
        """Join your voice channel"""
        if await self._join_voice_channel(ctx):
            await ctx.send(f"🔊 Joined **{ctx.author.voice.channel.name}**")

    @commands.command(name='leave')
    async def leave(self, ctx):
        """Leave voice channel"""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            self.current_voice_client = None
            await ctx.send("👋 Left voice channel")
        else:
            await ctx.send("❌ I'm not in a voice channel!")

    @commands.command(name='play')
    async def play(self, ctx, *, query: str):
        """Add a song to queue and start playing"""
        if not await self._join_voice_channel(ctx):
            return
            
        # Show searching message for non-URL queries
        if not query.startswith(('http://', 'https://')):
            search_msg = await ctx.send("🔍 Searching...")
        else:
            search_msg = None
            
        try:
            # Check if it's a playlist
            is_playlist = 'playlist' in query.lower() or 'list=' in query.lower()
            
            if is_playlist:
                await ctx.send("📥 Loading playlist... This may take a while for large playlists.")
                songs = self.music_handler.get_playlist(query)
                if songs:
                    self.queue.add_multiple(songs)
                    if search_msg:
                        await search_msg.delete()
                    await ctx.send(f"✅ Added **{len(songs)}** songs to queue")
                else:
                    if search_msg:
                        await search_msg.delete()
                    await ctx.send("❌ Could not load playlist")
                    return
            else:
                song = self.music_handler.get_song(query)
                if song:
                    self.queue.add(song)
                    if search_msg:
                        await search_msg.delete()
                    await ctx.send(f"✅ Added **{song['title']}** to queue")
                else:
                    if search_msg:
                        await search_msg.delete()
                    await ctx.send("❌ Could not load song")
                    return
                    
            # Start playing if not already playing
            if not ctx.voice_client.is_playing():
                await self._play_song(ctx)
                
        except Exception as e:
            if search_msg:
                await search_msg.delete()
            await ctx.send(f"❌ Error: {str(e)}")
            print(f"Error in play command: {e}")

    @commands.command(name='pause')
    async def pause(self, ctx):
        """Pause playback"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ Paused")
        else:
            await ctx.send("❌ Nothing is playing!")

    @commands.command(name='resume')
    async def resume(self, ctx):
        """Resume playback"""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ Resumed")
        else:
            await ctx.send("❌ Nothing is paused!")

    @commands.command(name='skip')
    async def skip(self, ctx, skip_to: int = None):
        """Skip current song or skip to specific position"""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await ctx.send("❌ Nothing is playing!")
            return
            
        if skip_to is None:
            # Skip current song
            ctx.voice_client.stop()
            await ctx.send("⏭️ Skipped")
        else:
            # Skip to specific position (1-indexed)
            if 1 <= skip_to <= self.queue.songs_count:
                # Set current index to position-1 and play
                self.queue.current_index = skip_to - 1
                ctx.voice_client.stop()
                await ctx.send(f"⏭️ Skipped to position **{skip_to}**")
            else:
                await ctx.send("❌ Invalid position!")

    @commands.command(name='queue')
    async def queue(self, ctx):
        """Show current queue"""
        if self.queue.is_empty():
            await ctx.send("❌ Queue is empty!")
            return
            
        songs = self.queue.get_all()
        current_index = self.queue.current_index
        
        embed = discord.Embed(title="🎵 Music Queue", color=discord.Color.green())
        
        # Show current song
        if current_index < len(songs):
            current_song = songs[current_index]
            current_duration = current_song.get('duration', 0)
            mins, secs = divmod(current_duration, 60)
            embed.add_field(
                name="▶️ Now Playing",
                value=f"**{current_song['title']}**\n`{mins}:{secs:02d}`",
                inline=False
            )
        
        # Show next songs (up to 10)
        next_songs = []
        for i in range(current_index + 1, min(current_index + 11, len(songs))):
            song = songs[i]
            duration = song.get('duration', 0)
            mins, secs = divmod(duration, 60)
            next_songs.append(f"**{i + 1}.** {song['title']} `({mins}:{secs:02d})`")
        
        if next_songs:
            embed.add_field(
                name="⏭️ Up Next",
                value="\n".join(next_songs),
                inline=False
            )
        
        # Show remaining count if more than 10
        remaining = len(songs) - (current_index + 11)
        if remaining > 0:
            embed.add_field(
                name="More Songs",
                value=f"... and **{remaining}** more songs",
                inline=False
            )
        
        # Show queue info
        total_songs = len(songs)
        embed.set_footer(text=f"Total songs: {total_songs} | Current position: {current_index + 1}")
        
        # Show loop status
        if self.queue.loop_mode != LoopMode.OFF:
            loop_status = "Single" if self.queue.loop_mode == LoopMode.SINGLE else "All"
            embed.set_footer(text=embed.footer.text + f" | 🔁 Loop: {loop_status}")
        
        await ctx.send(embed=embed)

    @commands.command(name='del')
    async def delete(self, ctx, position: int):
        """Delete song at position (1-indexed)"""
        if position < 1 or position > self.queue.songs_count:
            await ctx.send("❌ Invalid position!")
            return
            
        removed_song = self.queue.remove(position - 1)
        if removed_song:
            await ctx.send(f"❌ Removed: **{removed_song['title']}**")
        else:
            await ctx.send("❌ Could not remove song")

    @commands.command(name='shuffle')
    async def shuffle(self, ctx):
        """Shuffle the queue"""
        if self.queue.songs_count < 2:
            await ctx.send("❌ Not enough songs to shuffle!")
            return
            
        self.queue.shuffle()
        await ctx.send("🔀 Queue shuffled!")

    @commands.command(name='loop')
    async def loop(self, ctx, mode: str = None):
        """Toggle loop mode (single/all/off)"""
        if mode is None:
            # Cycle through modes using the queue's toggle method
            new_mode = self.queue.toggle_loop()
            if new_mode == LoopMode.OFF:
                await ctx.send("🔁 Loop: **OFF**")
            elif new_mode == LoopMode.ALL:
                await ctx.send("🔁 Loop All: **ON**")
            else:
                await ctx.send("🔁 Loop Single: **ON**")
        else:
            mode = mode.lower()
            if mode in ['single', 'one', 'current']:
                self.queue.set_loop_mode(LoopMode.SINGLE)
                await ctx.send("🔁 Loop Single: **ON**")
            elif mode in ['all', 'queue', 'everything']:
                self.queue.set_loop_mode(LoopMode.ALL)
                await ctx.send("🔁 Loop All: **ON**")
            elif mode in ['off', 'none', 'stop']:
                self.queue.set_loop_mode(LoopMode.OFF)
                await ctx.send("🔁 Loop: **OFF**")
            else:
                await ctx.send("❌ Invalid loop mode! Use: single, all, or off")

    @commands.command(name='clear')
    async def clear(self, ctx):
        """Clear the entire queue"""
        self.queue.clear()
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        await ctx.send("🗑️ Queue cleared!")

    @commands.command(name='music_help')
    async def music_help(self, ctx):
        """Show all available music commands"""
        embed = discord.Embed(
            title="🎵 Waffle Music Bot Help",
            description="Here are all the available music commands:",
            color=discord.Color.blue()
        )
        
        commands_list = [
            ("!join", "Join your voice channel"),
            ("!leave", "Leave voice channel"),
            ("!play <url/search>", "Add song to queue and start playing"),
            ("!pause", "Pause playback"),
            ("!resume", "Resume playback"),
            ("!skip [position]", "Skip current song or skip to position"),
            ("!queue", "Show current queue"),
            ("!del <position>", "Delete song at position (1-indexed)"),
            ("!shuffle", "Shuffle the queue"),
            ("!loop [single/all/off]", "Toggle loop mode"),
            ("!clear", "Clear entire queue"),
            ("!music_help", "Show this help message")
        ]
        
        for cmd, desc in commands_list:
            embed.add_field(name=cmd, value=desc, inline=False)
            
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MusicCog(bot))