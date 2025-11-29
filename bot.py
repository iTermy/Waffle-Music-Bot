import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='[', intents=intents)

async def load_cogs():
    await bot.load_extension('cogs.music_cog')

@bot.event
async def on_ready():
    print(f'✅ Bot is ready! Logged in as {bot.user}')
    print(f'Connected to {len(bot.guilds)} server(s)')

async def main():
    async with bot:
        await load_cogs()
        await bot.start(os.getenv('DISCORD_BOT_TOKEN'))

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())