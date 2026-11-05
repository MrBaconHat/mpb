import traceback
import asyncio
from cachetools import TTLCache

import discord
from discord import app_commands, ui
from discord.ext import commands

from bot.cogs.module import Module


class ConfigMenu(ui.LayoutView):
    def __init__(self, guild_id: int, module_class, parent):
        self.guild_id = guild_id
        self.module = module_class
        self.parent = parent

        self.db = module_class.db

        self.ra_config = {}

    async def initialize(self):
        config = await self.module.get_configs(self.guild_id) or []

        for row in config:
            guild_id = row["guild_id"]
            channel_id = row["channel_id"]
            message_id = row["message_id"]

            jump_url = f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
            
            self.ra_config[str(message_id)] = {
                "metadata": {
                    "guild_id": guild_id,
                    "channel_id": channel_id,
                    "message_id": message_id,
                    "jump_url": jump_url
                },
                "configuration": {
                    "header": None, # "Color Roles"
                    "description": None, # "Select your favorite color!"
                    "roles": None # Will be a dictionary with each role ID holding its button information such as button label and color.
                }
            }


class RoleAssignment(Module):
    def __init__(self, bot: commands.Bot):
        super().__init__(
            bot=bot,
            module_name="Role Assignments",
            module_description="to be added",
            internal_name="role_assignment",
            config_table="role_assignment_config",
            state_table="role_assignment_table"
        )

        self.db = self.bot.db

        self.message_ra_cache = TTLCache(maxsize=5000, ttl=300)

    async def initialize(self):
        await self.db.execute(f"""
        CREATE TABLE IF NOT EXISTS {self.CONFIG_TABLE} (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (message_id)
        )
        """)

        await self.db.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_{self.CONFIG_TABLE}_guild_channel
        ON {self.CONFIG_TABLE} (guild_id, channel_id)
        """)

        await self.db.commit()

    async def assign_role(self, interaction: discord.Interaction, version: str, data: str):
        guild = interaction.guild
        member = interaction.user
        
        if version == "v1":
            config_version = data[0]
            role_id = int(data[2])
            
            role = guild.get_role(role_id)
            if role is None:
                await interaction.response.send_message(
                    "This role no longer exists or isn't accessible to me.",
                    ephemeral=True
                )
                return

            try:
                if role in member.roles:
                    await member.remove_roles(role, reason="Role Assignment")
                else:
                    await member.add_roles(role, reason="Role Assignment")

            except discord.Forbidden:
                await interaction.response.send_message(
                    f"I don't have permission to manage this role.",
                    ephemeral=True
                )

            except discord.NotFound:
                await interaction.response.send_message(
                    "Role not found.",
                    ephemeral=True
                )
                

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return
            
        if interaction.type is not discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id")

        if custom_id is None:
            return

        if not custom_id.startswith("ra:"):
            return

        if not await self.is_enabled(interaction.guild.id):
            return

        split_data = custom_id.split(":")

        try:
            # Strict pattern across all versions.
            prefix = split_data[0]
            version = split_data[1]

            await self.assign_role(
                interaction=interaction,
                version=version, 
                data=split_data[2:]
            )
            
        except IndexError:
            await interaction.response.send_message(
                "Something went wrong.",
                ephemeral=True
            )
            return

    
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        if payload.guild_id is None:
            return

        if payload.cached_message:
            msg = payload.cached_message

            if not msg.components:
                return

            if msg.author.id != self.bot.user.id:
                return

        await self.db.delete_config(
            payload.guild_id, 
            where={"message_id": int(payload.message_id)}
        )


    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await self.db.delete_config(
            channel.guild.id,
            where={"channel_id": channel.id}
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleAssignment(bot))