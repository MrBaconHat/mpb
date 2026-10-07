import asyncio
import traceback

import discord
from discord import ui
from discord.ext import commands

from datetime import datetime, timezone

from bot.cogs.module import Module

from cachetools import TTLCache

from copy import deepcopy


class ConfigMenu(ui.LayoutView):
    def __init__(
        self,
        guild_id: int,
        module: Module,
        parent_view
    ):
        self.guild_id = guild_id 
        self.module = module
        self.parent_view = parent_view

        self.bot = self.module.bot
        self.storage = self.bot.storage

        self.config = self.storage.get_module(
            str(self.guild_id), self.module.INTERNAL_NAME, "config"
        )
        self.state = self.storage.get_module(
            str(self.guild_id), self.module.INTERNAL_NAME, "state"
        )

        self.sm_chnl_cache = {}
        self.sm_chnl_state = {}

        self.max_sm = 5  # Max sticky messages per guild

        super().__init__()


    async def initialize(self):
        self.sm_chnl_cache = await self.config.get("channels", {})
        self.sm_chnl_state = await self.state.get() or {}

        await self.config_page()

    async def sm_save(self, channel_id: int, message: str):
        await self.config.set(f"channels.{channel_id}.message", message)
        self.sm_chnl_cache[str(channel_id)] = {"message": message}

        cached = self.module.channel_cache.get(str(channel_id))

        last_message_id = (
            cached.get("last_message_id")
            if isinstance(cached, dict)
            else None
        )

        await self.state.set(
            f"{str(channel_id)}.last_message_id", last_message_id
        )

        self.module.channel_cache[str(channel_id)] = {
            "message": message,
            "last_message_id": last_message_id
        }

    async def sm_delete(self, channel_id: int):
        try:
            await self.config.delete(f"channels.{channel_id}")
            await self.state.delete(str(channel_id))
        except KeyError:
            pass

        self.sm_chnl_cache.pop(str(channel_id), None)
        self.sm_chnl_state.pop(str(channel_id), None)

        self.module.channel_cache.pop(str(channel_id), None)

    async def config_page(self):
        self.clear_items()

        sticky_msgs = deepcopy(self.sm_chnl_cache)

        container = ui.Container()
        container.add_item(
            ui.TextDisplay(f"### Sticky Messages List")
        )

        if len(sticky_msgs) <= 0:
            container.add_item(
                ui.TextDisplay(
                    "-# There are no sticky message set."
                )
            )

        for channel, message in sticky_msgs.items():
            try:
                message = message["message"]
            except KeyError:
                continue

            view_button = ui.Button(
                label="Edit",
                style=discord.ButtonStyle.gray, 
                custom_id=f"sm_edit:{channel}"
            )
            view_button.callback = self.edit_sm_button_callback

            container.add_item(
                ui.Section(
                    f"<#{channel}>\n-# **╰┈➤ {message if len(message) < 30 else f'{message[:30]}...'}**",
                    accessory=view_button
                )
            )
            
        # ======= Danger Zone ========
        container.add_item(ui.Separator())

        add_button = ui.Button(
            label="Add",
            disabled=len(sticky_msgs) >= self.max_sm
        )
        add_button.callback = self.add_sm_button_callback

        limit_indicator_button = ui.Button(
            label=f"{len(sticky_msgs)}/{self.max_sm}",
            style=discord.ButtonStyle.gray,
            disabled=True
        )

        delete_all_button = ui.Button(
            label="Delete",
            style=discord.ButtonStyle.red,
            disabled=len(sticky_msgs) <= 0
        )
        delete_all_button.callback = self.delete_sm_btn_callback

        danger_zone = ui.ActionRow(
            add_button,
            limit_indicator_button,
            delete_all_button
        )

        container.add_item(danger_zone)

        self.add_item(container)


    async def add_sm_button_callback(
        self, 
        i: discord.Interaction
    ):
        modal = ui.Modal(
            title="Add Sticky Message"
        )

        channel_select = ui.ChannelSelect(
            channel_types=[discord.ChannelType.text],
            placeholder="Select a channel...",
            required=True
        )
        message = ui.TextInput(
            label="Sticky Message Content",
            style=discord.TextStyle.paragraph,
            placeholder="Sticky message to send...",
            required=True,
            min_length=10,
            max_length=1000
        )

        modal.add_item(
            ui.Label(
                text="Sticky Channel",
                component=channel_select,
                description="Channel to send the sticky message in."
            )
        )
        modal.add_item(message)

        async def on_submit(i: discord.Interaction):
            channel = channel_select.values[0]
            message_content = message.value

            await self.sm_save(channel.id, message_content)
            await self.config_page()
            await self.parent_view.update_module_page(self)
            await i.response.edit_message(view=self.parent_view)

        modal.on_submit = on_submit

        await i.response.send_modal(modal)

    
    async def delete_sm_btn_callback(self, interaction: discord.Interaction):
        sticky_messages = deepcopy(self.sm_chnl_cache)

        modal = ui.Modal(
            title="Delete Sticky Message"
        )

        sm_select = ui.CheckboxGroup(
            min_values=1,
            max_values=len(sticky_messages)
        )

        for channel_id, data in sticky_messages.items():
            message = data["message"]

            channel = None
            try:
                channel = self.bot.get_channel(int(channel_id)) or await self.bot.fetch_channel(int(channel_id))
            except (discord.NotFound, discord.Forbidden):
                continue

            if channel is None:
                continue

            sm_select.add_option(
                label=f"#{channel.name}",
                default=False,
                value=channel_id
            )

        modal.add_item(
            ui.Label(
                text="Sticky messages to delete",
                component=sm_select
            )
        )

        # === Modal's Callback ===
        async def on_sm_delete_modal_submit(interaction: discord.Interaction):
            selected_sms = sm_select.values
            for chnl_id in selected_sms:
                try:
                    await self.sm_delete(chnl_id)

                except KeyError:
                    continue

            await self.config_page()
            await self.parent_view.update_module_page(self)
            await interaction.response.edit_message(view=self.parent_view)
                

        modal.on_submit = on_sm_delete_modal_submit

        await interaction.response.send_modal(modal)

    async def edit_sm_button_callback(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]

        channel_id = custom_id.split(":")[1]
        message = self.sm_chnl_cache.get(str(channel_id), {}).get("message")

        modal = ui.Modal(
            title="Edit Sticky Message",
            custom_id=f"edit_sm:{channel_id}"
        )

        channel_select = ui.ChannelSelect(
            channel_types=[discord.ChannelType.text],
            placeholder="Select a channel...",
            required=True,
            default_values=[discord.Object(id=channel_id)]
        )
        message = ui.TextInput(
            label="Sticky Message Content",
            style=discord.TextStyle.paragraph,
            placeholder="Sticky message to send...",
            required=True,
            min_length=10,
            max_length=1000,
            default=message
        )

        modal.add_item(
            ui.Label(
                text="Sticky Channel",
                component=channel_select,
                description="Channel to send the sticky message in."
            )
        )
        modal.add_item(message)

        async def edit_sm_modal_callback(i: discord.Interaction):
            custom_id = i.data["custom_id"]

            old_channel_id = int(custom_id.split(":")[1])
            new_channel_id = channel_select.values[0].id
            new_message = message.value

            await self.sm_save(new_channel_id, new_message)

            if old_channel_id != new_channel_id:
                last_message_id = await self.state.get(str(old_channel_id))
                if last_message_id:
                    await self.state.set(str(new_channel_id), last_message_id)
                    self.module.channel_cache[str(new_channel_id)]["last_message_id"] = last_message_id
                    
                await self.sm_delete(old_channel_id)

            await self.config_page()
            await self.parent_view.update_module_page(self)
            await i.response.edit_message(view=self.parent_view)

        modal.on_submit = edit_sm_modal_callback

        await interaction.response.send_modal(modal)


class StickyMessage(Module):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.storage = bot.storage

        self.lock = TTLCache(maxsize=10000, ttl=60)
        
        self.debounce = 3
        self.guild_channel_debounce = TTLCache(maxsize=10000, ttl=60)
        
        self.channel_cache = TTLCache(maxsize=10000, ttl=500)

        super().__init__(
            bot=self.bot,
            module_name="Sticky Message",
            module_description="Keep a message at the bottom of a channel.",
            internal_name="sticky_message"
        )

    async def build_config_page(
        self,
        guild_id: str | int,
        parent_view
    ) -> list[ui.Item]:
        view = ConfigMenu(int(guild_id), self, parent_view)
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

        if not isinstance(message.channel, discord.TextChannel):
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
            self.guild_channel_debounce[str(message.channel.id)] = datetime.now(timezone.utc)
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
            
            channel_config = self.channel_cache.get(str(message.channel.id))

            if channel_config is False:
                return
                
            if channel_config is None:
                channel_config = await config.get(f"channels.{message.channel.id}")
                if channel_config is None:
                    self.channel_cache[str(message.channel.id)] = False
                    return
                    
                data = {
                    "message": channel_config["message"],
                    "last_message_id": await state.get(f"{message.channel.id}.last_message_id",  None)
                }

                self.channel_cache[str(message.channel.id)] = data
                channel_config = data

            last_message_id = channel_config.get("last_message_id")

            if last_message_id:
                last_message_id = int(last_message_id)
                
                if last_message_id > message.id:
                    return

                try:
                    old_message = message.channel.get_partial_message(last_message_id)
                    if old_message:
                        await old_message.delete()

                except (discord.Forbidden, discord.NotFound):
                    pass

            while True:
                timer = self.guild_channel_debounce.get(
                    str(message.channel.id)
                )

                if timer is None:
                    break

                elapsed = datetime.now(timezone.utc) - timer
                remaining = self.debounce - elapsed.total_seconds()

                if remaining <= 0:
                    break

                await asyncio.sleep(remaining)

            try:
                new_message = await message.channel.send(channel_config.get("message"))
                try:
                    await state.update(
                        str(message.channel.id),
                        {"last_message_id": str(new_message.id)},
                        strict_keys=True
                    )

                    self.channel_cache[str(message.channel.id)]["last_message_id"] = str(new_message.id)
                except KeyError:
                    pass

            except discord.NotFound:
                await config.delete(f"channels.{str(message.channel.id)}")
                await state.delete(str(message.channel.id))

                self.channel_cache.pop(str(message.channel.id), None)

            except discord.Forbidden:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(StickyMessage(bot))