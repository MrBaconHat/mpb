import asyncio
import traceback

import discord
from discord import ui
from discord.ext import commands

from datetime import datetime, timezone

from bot.cogs.module import Module

from cachetools import TTLCache


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

        self.max_sm = 5  # Max sticky messages per guild

        super().__init__()


    async def initialize(self):
        await self.config_page()

    async def config_page(self):
        self.clear_items()

        config = await self.config.get("channels", {})

        container = ui.Container()
        container.add_item(
            ui.TextDisplay(f"### Sticky Messages List")
        )

        if len(config) <= 0:
            container.add_item(
                ui.TextDisplay(
                    "-# There are no sticky message set."
                )
            )

        for channel, message in config.items():
            try:
                message = message["message"]
            except KeyError:
                continue

            view_button = ui.Button(
                label="View",
                style=discord.ButtonStyle.gray, 
                custom_id=f"sm_view:{channel}"
            )
            view_button.callback = self.view_btn_callback

            container.add_item(
                ui.Section(
                    f"<#{channel}>\n-# **╰┈➤ {message if len(message) < 70 else f'{message[:70]}...'}**",
                    accessory=view_button
                )
            )

        # ======= Danger Zone ========
        container.add_item(ui.Separator())

        add_button = ui.Button(
            label="Add",
            disabled=len(config) >= self.max_sm
        )
        add_button.callback = self.add_sm_button_callback

        limit_indicator_button = ui.Button(
            label=f"{len(config)}/{self.max_sm}",
            style=discord.ButtonStyle.gray,
            disabled=True
        )

        delete_all_button = ui.Button(
            label="Delete All",
            style=discord.ButtonStyle.red,
            disabled=len(config) <= 0
        )
        delete_all_button.callback = self.delete_all_sm_btn_callback

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
        try:
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

                await self.config.set(
                    f"channels.{str(channel.id)}.message", message_content
                )

                await self.parent_view.update_page()
                await i.response.edit_message(view=self.parent_view)

            modal.on_submit = on_submit

            await i.response.send_modal(modal)

        except Exception as e:
            traceback.print_exception(
                type(e), e, e.__traceback__
            )

    async def delete_all_sm_btn_callback(self, interaction: discord.Interaction):
        await self.config.delete("channels")
        channels = await self.state.get()
        for channel in channels:
            await self.state.delete(channel)
            
        await self.parent_view.update_page()
        await interaction.response.edit_message(view=self.parent_view)

    async def view_sm_page(self, channel_id: int):
        self.clear_items()

        sm = await self.config.get(f"channels.{channel_id}", None)
        if sm is None:
            raise KeyError(channel_id)

        try:
            message = sm["message"]
        except KeyError:
            return

        container = ui.Container()

        async def go_back_btn_callback(i: discord.Interaction):
            await self.parent_view.update_page()
            await i.response.edit_message(view=self.parent_view)

        go_back_btn = ui.Button(
            label="<-",
            style=discord.ButtonStyle.gray
        )
        go_back_btn.callback = go_back_btn_callback

        container.add_item(
            ui.ActionRow(
                go_back_btn
            )
        )

        # --- Sticky Message Info ---
        container.add_item(
            ui.TextDisplay(
                f"## <#{channel_id}>"
            )
        )
        container.add_item(
            ui.TextDisplay(
                "**Message:**\n"
                f"-# **╰┈➤{message if len(message) < 200 else f'{message[:200]}...'}**"
            )
        )

        # --- Management Zone ---
        async def edit_sm_button_callback(interaction: discord.Interaction):
            custom_id = interaction.data["custom_id"]

            channel_id = custom_id.split(":")[1]
            message = await self.config.get(
                f"channels.{channel_id}.message"
            )

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

            async def edit_sm_modal_callback(i: discord.Interaction):
                custom_id = i.data["custom_id"]

                old_channel_id = int(custom_id.split(":")[1])
                new_channel_id = channel_select.values[0].id
                new_message = message.value

                await self.config.set(
                    f"channels.{new_channel_id}.message",
                    new_message
                )

                if old_channel_id != new_channel_id:
                    await self.config.delete(f"channels.{old_channel_id}")
                    last_message_id = await self.state.get(str(old_channel_id))
                    await self.state.set(str(new_channel_id), last_message_id)
                    await self.state.delete(str(old_channel_id))

                await self.view_sm_page(int(new_channel_id))
                await i.response.edit_message(view=self)

            modal.on_submit = edit_sm_modal_callback

            await interaction.response.send_modal(modal)


        async def delete_sm_btn_callback(
            interaction: discord.Interaction
        ):
            custom_id = interaction.data["custom_id"]

            channel_id = custom_id.split(":")[1]

            try:
                await self.config.delete(f"channels.{channel_id}")
                await self.state.delete(str(channel_id))
            except KeyError:
                pass

            await self.parent_view.update_page()
            await interaction.response.edit_message(view=self.parent_view)

        edit_sm_btn = ui.Button(
            label="Edit",
            style=discord.ButtonStyle.grey,
            custom_id=f"edit_sm:{channel_id}"
        )
        edit_sm_btn.callback = edit_sm_button_callback

        delete_sm_btn = ui.Button(
            label="Delete",
            style=discord.ButtonStyle.red ,
            custom_id=f"delete_sm:{channel_id}"
        )
        delete_sm_btn.callback = delete_sm_btn_callback

        container.add_item(
           ui.ActionRow(
               edit_sm_btn,
               delete_sm_btn
           )
        )

        self.add_item(container)

    async def view_btn_callback(
        self,
        i: discord.Interaction
    ):
        custom_id = i.data["custom_id"]
        channel_id = custom_id.split(":", 2)[1]

        await self.view_sm_page(int(channel_id))
        await i.response.edit_message(view=self)


class StickyMessage(Module):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.storage = bot.storage

        self.lock = TTLCache(maxsize=100, ttl=60)
        self.debounce = 3
        self.guild_channel_debounce = TTLCache(maxsize=1000, ttl=60)
        self.channel_last_message = TTLCache(maxsize=10000, ttl=500)

        super().__init__(
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
        print("message sent")
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

            channel_config = await config.get(f"channels.{message.channel.id}")
            if channel_config is None:
                return

            last_message_id = self.channel_last_message.get(str(message.channel.id)) or await state.get(f"{message.channel.id}.last_message_id", 0)
            if int(last_message_id) > message.id:
                return

            try:
                old_message = message.channel.get_partial_message(int(last_message_id))

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
                await state.set(f"{message.channel.id}.last_message_id", str(new_message.id))
                self.channel_last_message[str(message.channel.id)] = new_message.id

            except discord.NotFound:
                await config.delete(str(message.channel.id))
                await state.delete(str(message.channel.id))

            except discord.Forbidden:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(StickyMessage(bot))