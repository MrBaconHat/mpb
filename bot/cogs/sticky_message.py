import asyncio

import discord
from discord import ui
from discord.ext import commands

from bot.cogs.module import Module

from cachetools import TTLCache


class ConfigMenu(ui.LayoutView):
    def __init__(
        self,
        guild_id: int,
        module: Module
    ):
        self.guild_id = guild_id 
        self.module = module

        self.bot = self.module.bot
        self.storage = self.bot.storage
        
        self.config = self.storage.get_module(str(self.guild_id), self.module.INTERNAL_NAME, "config")

        self.max_sm = 5

        super().__init__()


    async def initialize(self):
        config = await self.config.get() or {}
        
        container = ui.Container()
        for channel, message in config.items():
            if channel == "is_enabled":
                continue

            view_button = ui.Button(
                label="View",
                style=discord.ButtonStyle.gray, 
                custom_id=f"sm_view:{channel}"
            )
            # view_button.callback = ...

            container.add_item(
                ui.Section(
                    f"<#{channel}>\n-# {message if len(message) < 70 else f'{message[:70]}...'}",
                    accessory=view_button
                )
            )

        self.add_item(container)


class StickyMessage(Module):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.storage = bot.storage

        self.lock = TTLCache(maxsize=100, ttl=60)

        super().__init__(
            module_name="Sticky Message",
            module_description="Keep a message at the bottom of a channel.",
            internal_name="sticky_message"
        )

    async def build_config_page(
        self,
        guild_id: str | int
    ) -> list[ui.Item] | None:
        view = ConfigMenu(int(guild_id), self)
        await view.initialize()

        items = []

        for item in view.children:
            if isinstance(item, ui.Container):
                for component in item.children:
                    items.append(component)

        return items
    

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