import traceback
import asyncio
from cachetools import TTLCache

import discord
from discord import app_commands, ui
from discord.ext import commands

from bot.cogs.module import Module


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

    async def initialize(self):
        await self.db.execute(f"""
        CREATE TABLE IS NOT EXISTS {self.CONFIG_TABLE} (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL
            PRIMARY KEY (message_id)
        )
        """)

    def extract_data(self, version: str, data: str):
        if version == "v1":
            config_version = data[0]
            action = data[1]
            role_id = data[2]

        else:
            raise ValueError(f"Invalid Version: {version}")

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type is not discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id")

        if custom_id is None:
            return

        if not custom_id.startswith("ra"):
            return

        split_data = custom_id.split(":")

        try:
            # Strict pattern across all versions.
            prefix = split_data[0]
            version = split_data[1]

            self.extract_data(version, split_data[2:])
        except ValueError:
            return
        
        except IndexError:
            return


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleAssignment(bot))