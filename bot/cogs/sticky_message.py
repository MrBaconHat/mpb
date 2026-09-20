import asyncio

import discord
from discord.ext import commands

from cachetools import TTLCache


class StickyMessage(commands.Cog):
    MODULE_NAME = "Sticky Message"
    INTERNAL_NAME = "sticky_message"
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.storage = bot.storage

        self.lock = TTLCache(maxsize=100, ttl=60)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id == self.bot.user.id:
            return
            
        if message.guild is None:
            return

        enabled = await self.storage.is_enabled(
            message.guild.id, 
            self.INTERNAL_NAME
        )
        if not enabled:
            return

        lock = self.lock.setdefault(
            str(message.channel.id), 
            asyncio.Lock()
        )

        if lock.locked():
            return

        async with lock:
            config = self.storage.get_module(
                message.guild.id, 
                self.INTERNAL_NAME, 
                "config"
            )
            state = self.storage.get_module(
                message.guild.id, 
                self.INTERNAL_NAME, 
                "state"
            )

            channel_config = await config.get(str(message.channel.id))
            if channel_config is None:
                return

            last_message_id = await state.get(f"{message.channel.id}.last_message_id")

            old_message = None
            if last_message_id:
                if int(last_message_id) > message.id:
                    return
                    
                try:
                    old_message = await message.channel.fetch_message(int(last_message_id))
                except (discord.NotFound, discord.Forbidden):
                    old_message = None

            if old_message:
                try:
                    await old_message.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass

            try:
                new_message = await message.channel.send(channel_config.get("message"))
                await state.set(f"{message.channel.id}.last_message_id", str(new_message.id))
            
            except discord.NotFound:
                await config.delete(str(message.channel.id))
                await state.delete(str(message.channel.id))

            except discord.Forbidden:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(StickyMessage(bot))