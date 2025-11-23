import discord
from discord.ext import commands
import asyncio
from music_handler import MusicHandler
from music_queue import MusicQueue

class MusicCog(commands.Cog):
    """Music commands cog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.music_handler = MusicHandler()
        self.queue = MusicQueue()
        self.current_voice_client = None
    
    @commands.command()
    async def join(self, ctx):
        """Join your voice channel"""
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            
            # If already in a voice channel, move to new one
            if ctx.voice_client:
                await ctx.voice_client.move_to(channel)
            else:
                await channel.connect()
            
            await ctx.send(f"🔊 Joined **{channel.name}**")
        else:
            await ctx.send("❌ You're not in a voice channel!")
    
    @commands.command()
    async def leave(self, ctx):
        """Leave voice channel"""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("👋 Left voice channel")
        else:
            await ctx.send("❌ I'm not in a voice channel!")
    
    @commands.command()
    async def add(self, ctx, *, url: str):
        """Add a song to the queue"""
        await ctx.send("🔍 Adding song...")
        
        try:
            # Check if it's a playlist
            if 'playlist' in url or 'list=' in url:
                songs = self.music_handler.get_playlist(url)
                if songs:
                    self.queue.add_multiple(songs)
                    await ctx.send(f"✅ Added **{len(songs)}** songs to queue")
                else:
                    await ctx.send("❌ Could not load playlist")
            else:
                # Single song
                song = self.music_handler.get_song(url)
                if song:
                    self.queue.add(song)
                    position = len(self.queue.songs)
                    await ctx.send(f"✅ Added **{song['title']}** (Position #{position})")
                else:
                    await ctx.send("❌ Could not load song")
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")
    
    @commands.command()
    async def play(self, ctx):
        """Start playing the queue"""
        # Join voice if not already in
        if not ctx.voice_client:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("❌ You need to be in a voice channel!")
                return
        
        # Check if queue is empty
        if self.queue.is_empty():
            await ctx.send("❌ Queue is empty! Add songs with `!add <url>`")
            return
        
        # Start playing
        await self._play_song(ctx)
    
    async def _play_song(self, ctx):
        """Internal method to play current song"""
        song = self.queue.get_current()
        
        if not song:
            await ctx.send("✅ Queue finished!")
            return
        
        # Get fresh URL (in case it expired)
        if 'webpage_url' in song:
            try:
                song = self.music_handler.get_song(song['webpage_url'])
                if not song:
                    await ctx.send("❌ Error loading song, skipping...")
                    self.queue.next()
                    await self._play_song(ctx)
                    return
            except Exception as e:
                await ctx.send("❌ Error refreshing song, skipping...")
                self.queue.next()
                await self._play_song(ctx)
                return
        
        # Create audio source
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        
        try:
            audio_source = discord.FFmpegPCMAudio(song['url'], **ffmpeg_options)
        except Exception as e:
            await ctx.send("❌ Error creating audio source, skipping...")
            self.queue.next()
            await self._play_song(ctx)
            return
        
        # Play with callback for when song ends
        def after_playing(error):
            if error:
                print(f"Playback error: {error}")
            
            # Move to next song
            coro = self._after_song(ctx)
            fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
            try:
                fut.result()
            except Exception as e:
                print(f"Error in after_playing: {e}")
        
        ctx.voice_client.play(audio_source, after=after_playing)
        
        # Send now playing message
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"**{song['title']}**",
            color=discord.Color.blue()
        )
        
        if song.get('duration'):
            mins = song['duration'] // 60
            secs = song['duration'] % 60
            embed.add_field(name="Duration", value=f"{mins}:{secs:02d}")
        
        if song.get('thumbnail'):
            embed.set_thumbnail(url=song['thumbnail'])
        
        await ctx.send(embed=embed)
    
    async def _after_song(self, ctx):
        """Called after a song finishes"""
        # Check if there's a next song
        if self.queue.has_next():
            self.queue.next()
            await self._play_song(ctx)
        else:
            await ctx.send("✅ Queue finished!")
    
    @commands.command()
    async def pause(self, ctx):
        """Pause playback"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ Paused")
        else:
            await ctx.send("❌ Nothing is playing!")
    
    @commands.command()
    async def resume(self, ctx):
        """Resume playback"""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ Resumed")
        else:
            await ctx.send("❌ Nothing is paused!")
    
    @commands.command()
    async def skip(self, ctx):
        """Skip current song"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()  # This triggers after_playing callback
            await ctx.send("⏭️ Skipped")
        else:
            await ctx.send("❌ Nothing is playing!")
    
    @commands.command()
    async def queue(self, ctx):
        """Show current queue"""
        if self.queue.is_empty():
            await ctx.send("❌ Queue is empty!")
            return
        
        current_idx, total = self.queue.get_position()
        songs = self.queue.get_all()
        
        # Build embed
        embed = discord.Embed(
            title="🎵 Music Queue",
            color=discord.Color.blue()
        )
        
        # Show current song
        if current_idx < len(songs):
            current = songs[current_idx]
            embed.add_field(
                name="▶️ Now Playing",
                value=f"**{current['title']}**",
                inline=False
            )
        
        # Show next songs (max 10)
        next_songs = songs[current_idx + 1:current_idx + 11]
        if next_songs:
            queue_text = ""
            for i, song in enumerate(next_songs, start=1):
                queue_text += f"{current_idx + i + 1}. {song['title']}\n"
            
            embed.add_field(
                name="⏭️ Up Next",
                value=queue_text,
                inline=False
            )
        
        # Footer info
        remaining = total - current_idx - 1
        if remaining > 10:
            embed.set_footer(text=f"... and {remaining - 10} more songs")
        
        if self.queue.loop_enabled:
            embed.set_footer(text=f"{embed.footer.text if embed.footer else ''} | 🔁 Loop: ON")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="del")
    async def delete(self, ctx, position: int):
        """Delete song at position (1-indexed)"""
        if position < 1 or position > len(self.queue.songs):
            await ctx.send("❌ Invalid position!")
            return
        
        removed = self.queue.remove(position - 1)
        if removed:
            await ctx.send(f"❌ Removed: **{removed['title']}**")
        else:
            await ctx.send("❌ Could not remove song")
    
    @commands.command()
    async def shuffle(self, ctx):
        """Shuffle the queue"""
        if len(self.queue.songs) <= 1:
            await ctx.send("❌ Not enough songs to shuffle!")
            return
        
        self.queue.shuffle()
        await ctx.send("🔀 Queue shuffled!")
    
    @commands.command()
    async def loop(self, ctx):
        """Toggle loop mode"""
        is_looping = self.queue.toggle_loop()
        status = "**ON**" if is_looping else "**OFF**"
        await ctx.send(f"🔁 Loop: {status}")
    
    @commands.command()
    async def clear(self, ctx):
        """Clear the entire queue"""
        self.queue.clear()
        
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        
        await ctx.send("🗑️ Queue cleared!")

async def setup(bot):
    """Load the cog"""
    await bot.add_cog(MusicCog(bot))