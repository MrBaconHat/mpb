import asyncio
from bot.bot import bot


async def main():
    await bot.start_bot()

asyncio.run(main())