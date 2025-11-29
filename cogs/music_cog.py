import discord
from discord.ext import commands
import asyncio
from music_handler import MusicHandler
from music_queue import MusicQueue, LoopMode

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_handler = MusicHandler()
        self.queue = MusicQueue()
        self.current_voice_client = None
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member == self.bot.user and before.channel and not after.channel:
            self._cleanup_queue()
    
    def _cleanup_queue(self):
        self.queue.clear()
        self.current_voice_client = None
    
    @commands.command()
    async def join(self, ctx):
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            
            if not ctx.voice_client and self.current_voice_client:
                self._cleanup_queue()
            
            if ctx.voice_client:
                await ctx.voice_client.move_to(channel)
            else:
                await channel.connect()
            
            self.current_voice_client = ctx.voice_client
            await ctx.send(f"🔊 Joined **{channel.name}**")
        else:
            await ctx.send("❌ You're not in a voice channel!")
    
    @commands.command()
    async def leave(self, ctx):
        if ctx.voice_client:
            self._cleanup_queue()
            await ctx.voice_client.disconnect()
            await ctx.send("👋 Left voice channel (queue cleared)")
        else:
            await ctx.send("❌ I'm not in a voice channel!")
    
    @commands.command()
    async def add(self, ctx, *, url: str):
        await ctx.send("🔍 Adding song...")
        
        try:
            if 'playlist' in url or 'list=' in url:
                songs = self.music_handler.get_playlist(url)
                if songs:
                    self.queue.add_multiple(songs)
                    await ctx.send(f"✅ Added **{len(songs)}** songs to queue")
                else:
                    await ctx.send("❌ Could not load playlist")
            else:
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
        if not ctx.voice_client:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
                self.current_voice_client = ctx.voice_client
            else:
                await ctx.send("❌ You need to be in a voice channel!")
                return
        
        if self.queue.is_empty():
            await ctx.send("❌ Queue is empty! Add songs with `[add <url>`")
            return
        
        await self._play_song(ctx)
    
    async def _play_song(self, ctx):
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await ctx.send("❌ Bot is not in voice channel anymore")
            self._cleanup_queue()
            return
        
        song = self.queue.get_current()
        
        if not song:
            await ctx.send("✅ Queue finished!")
            return
        
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
        
        def after_playing(error):
            if error:
                print(f"Playback error: {error}")
            
            coro = self._after_song(ctx)
            fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
            try:
                fut.result()
            except Exception as e:
                print(f"Error in after_playing: {e}")
        
        ctx.voice_client.play(audio_source, after=after_playing)
        
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
        
        loop_mode = self.queue.get_loop_mode()
        if loop_mode == LoopMode.SINGLE:
            embed.set_footer(text="🔂 Loop: Single")
        elif loop_mode == LoopMode.ALL:
            embed.set_footer(text="🔁 Loop: All")
        
        await ctx.send(embed=embed)
    
    async def _after_song(self, ctx):
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            self._cleanup_queue()
            return
        
        loop_mode = self.queue.get_loop_mode()
        
        if loop_mode == LoopMode.SINGLE:
            await self._play_song(ctx)
        elif loop_mode == LoopMode.ALL:
            current_song = self.queue.songs.pop(self.queue.current_index)
            self.queue.songs.append(current_song)
            await self._play_song(ctx)
        else:
            self.queue.songs.pop(self.queue.current_index)
            
            if self.queue.current_index < len(self.queue.songs):
                await self._play_song(ctx)
            else:
                await ctx.send("✅ Queue finished!")
    
    @commands.command()
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ Paused")
        else:
            await ctx.send("❌ Nothing is playing!")
    
    @commands.command()
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ Resumed")
        else:
            await ctx.send("❌ Nothing is paused!")
    
    @commands.command()
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            loop_mode = self.queue.get_loop_mode()
            ctx.voice_client.stop()
            
            if loop_mode == LoopMode.SINGLE:
                await ctx.send("⏭️ Skipped (song will repeat due to loop single)")
            elif loop_mode == LoopMode.ALL:
                await ctx.send("⏭️ Skipped and moved to end of playlist")
            else:
                await ctx.send("⏭️ Skipped")
        else:
            await ctx.send("❌ Nothing is playing!")
    
    @commands.command()
    async def queue(self, ctx):
        if self.queue.is_empty():
            await ctx.send("❌ Queue is empty!")
            return
        
        current_idx, total = self.queue.get_position()
        all_songs = self.queue.get_all()
        
        # Calculate total pages (10 songs per page after the "Now Playing" section)
        # Page 1 shows: Now Playing + next 10 songs
        # Page 2+ shows: 10 songs each
        songs_after_current = total - (current_idx + 1)
        
        if songs_after_current <= 10:
            # No pagination needed - single page
            embed = self._create_queue_page(all_songs, current_idx, 0, 1)
            await ctx.send(embed=embed)
            return
        
        # Calculate total pages
        total_pages = (songs_after_current + 9) // 10  # Ceiling division
        current_page = 0
        
        # Create and send initial page
        embed = self._create_queue_page(all_songs, current_idx, current_page, total_pages)
        message = await ctx.send(embed=embed)
        
        # Add reaction buttons
        await message.add_reaction('⬅️')
        await message.add_reaction('➡️')
        
        # Reaction check function
        def check(reaction, user):
            return (
                user == ctx.author and
                reaction.message.id == message.id and
                str(reaction.emoji) in ['⬅️', '➡️']
            )
        
        # Pagination loop
        while True:
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                
                # Handle navigation
                if str(reaction.emoji) == '➡️' and current_page < total_pages - 1:
                    current_page += 1
                elif str(reaction.emoji) == '⬅️' and current_page > 0:
                    current_page -= 1
                
                # Update embed
                embed = self._create_queue_page(all_songs, current_idx, current_page, total_pages)
                await message.edit(embed=embed)
                
                # Remove user's reaction
                try:
                    await message.remove_reaction(reaction, user)
                except discord.errors.Forbidden:
                    pass  # Bot doesn't have permission to remove reactions
                
            except asyncio.TimeoutError:
                # Timeout reached - clear reactions
                try:
                    await message.clear_reactions()
                except discord.errors.Forbidden:
                    pass  # Bot doesn't have permission to clear reactions
                break
    
    def _create_queue_page(self, all_songs, current_idx, page, total_pages):
        """Create an embed for a specific page of the queue"""
        embed = discord.Embed(
            title="🎵 Music Queue",
            color=discord.Color.blue()
        )
        
        # Always show "Now Playing" on page 1
        if page == 0 and current_idx < len(all_songs):
            current_song = all_songs[current_idx]
            embed.add_field(
                name="▶️ Now Playing",
                value=f"**{current_song['title']}** (Position #{current_idx + 1})",
                inline=False
            )
        
        # Calculate which songs to show on this page
        if page == 0:
            # Page 1: Show next 10 songs after current
            start_idx = current_idx + 1
            end_idx = min(start_idx + 10, len(all_songs))
        else:
            # Page 2+: Show 10 songs per page
            start_idx = current_idx + 1 + (page * 10)
            end_idx = min(start_idx + 10, len(all_songs))
        
        # Build the song list for this page
        if start_idx < len(all_songs):
            queue_text = ""
            for i in range(start_idx, end_idx):
                song = all_songs[i]
                queue_text += f"**{i + 1}.** {song['title']}\n"
            
            if queue_text:
                embed.add_field(
                    name="⏭️ Up Next" if page == 0 else f"⏭️ Queue (continued)",
                    value=queue_text,
                    inline=False
                )
        
        # Build footer
        footer_parts = []
        
        # Add page indicator if multiple pages
        if total_pages > 1:
            footer_parts.append(f"Page {page + 1} of {total_pages}")
        
        # Add loop mode indicator
        loop_mode = self.queue.get_loop_mode()
        if loop_mode == LoopMode.SINGLE:
            footer_parts.append("🔂 Loop: Single")
        elif loop_mode == LoopMode.ALL:
            footer_parts.append("🔁 Loop: All")
        
        if footer_parts:
            embed.set_footer(text=" | ".join(footer_parts))
        
        return embed
    
    @commands.command(name="del")
    async def delete(self, ctx, position: int):
        if position < 1 or position > len(self.queue.songs):
            await ctx.send("❌ Invalid position!")
            return
        
        removed = self.queue.remove(position - 1)
        if removed:
            await ctx.send(f"❌ Removed: **{removed['title']}** (was position #{position})")
        else:
            await ctx.send("❌ Could not remove song")
    
    @commands.command()
    async def shuffle(self, ctx):
        if len(self.queue.songs) <= 1:
            await ctx.send("❌ Not enough songs to shuffle!")
            return
        
        self.queue.shuffle()
        await ctx.send("🔀 Queue shuffled!")
    
    @commands.command()
    async def unshuffle(self, ctx):
        if not self.queue.is_shuffled:
            await ctx.send("❌ Queue is not shuffled!")
            return
        
        self.queue.unshuffle()
        await ctx.send("↩️ Queue restored to original order!")
    
    @commands.group(invoke_without_command=True)
    async def loop(self, ctx):
        new_mode = self.queue.cycle_loop_mode()
        
        if new_mode == LoopMode.SINGLE:
            await ctx.send("🔂 Loop Single: **ON**")
        elif new_mode == LoopMode.ALL:
            await ctx.send("🔁 Loop All: **ON**")
        else:
            await ctx.send("🔁 Loop: **OFF**")
    
    @loop.command(name='single')
    async def loop_single(self, ctx):
        self.queue.set_loop_mode(LoopMode.SINGLE)
        await ctx.send("🔂 Loop Single: **ON**")
    
    @loop.command(name='all')
    async def loop_all(self, ctx):
        self.queue.set_loop_mode(LoopMode.ALL)
        await ctx.send("🔁 Loop All: **ON**")
    
    @loop.command(name='off')
    async def loop_off(self, ctx):
        self.queue.set_loop_mode(LoopMode.OFF)
        await ctx.send("🔁 Loop: **OFF**")
    
    @commands.command()
    async def clear(self, ctx):
        self.queue.clear()
        
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        
        await ctx.send("🗑️ Queue cleared!")
    
    @commands.command()
    async def delall(self, ctx):
        await self.clear(ctx)

async def setup(bot):
    await bot.add_cog(MusicCog(bot))