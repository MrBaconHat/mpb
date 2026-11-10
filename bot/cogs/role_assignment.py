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


class DataExtractor:
    def __init__(self):
        self.extractors = {"v1": self._v1_data_extractor}

    def _v1_data_extractor(self, data: list[str]):
        prefix = None
        version = None
        config_version = None
        role_id = None
        
        try:
            prefix = data[0]
            version = data[1]
            config_version = data[2]
            role_id = data[3]
        except IndexError:
            pass

        return (prefix, version, config_version, role_id)
            
    def extract(self, data: str):
        split_data = data.split(":")
        
        prefix = split_data[0]
        version = split_data[1]

        extractor = self.extractors.get(version)
        if extractor is None:
            raise ValueError("Invalid Version")
            
        return extractor(split_data)


class RoleAssignmentCallbacks:
    def __init__(self, module):
        self.module = module
        self.bot = module.bot

        self.extract = DataExtractor()

    async def _get_role(self, guild: discord.Guild, role_id: int) -> discord.Role | None:
        try:
            role = guild.get_role(role_id) or await guild.fetch_role(role_id)
            
        except (discord.Forbidden, discord.NotFound):
            return None
            
        return role

    async def on_button_callback(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]
        prefix, version, config_version, role_id = self.extract.extract(custom_id)

        guild = interaction.guild
        
        member = interaction.user

        role = await self._get_role(guild, int(role_id))

        if role is None:
            await interaction.response.send_message(
                f"**Error:** Role <@&{role_id}>({role_id}) not found.",
                ephemeral=True
            )
            return

        user_facing_message = ""

        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Role Assignment")
                user_facing_message = f"**Successfully:** Removed {role.mention} from you."
                
            else:
                await member.add_roles(role, reason="Role Assignment")
                user_facing_message = f"**Successfully:** Added {role.mention} to you."
                
        except discord.Forbidden:
            user_facing_message = f"**Error:** I do not have permission to add roles. \nPlease make sure i have **Manage Roles** permission and my role is above: {role.mention}"

        await interaction.response.send_message(
            user_facing_message, 
            ephemeral=True
        )

    async def on_select_menu_callback(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]
        values = interaction.data.get("values", [])
        
        split = custom_id.split(":")
        
        try:
            prefix = split[0]
            version = split[1]
            config_version = split[2]
            
        except IndexError:
            return

        message = interaction.message
        
        container = message.components[0]
        action_row = container.children[2]
        select_menu = action_row.children[0]

        guild = interaction.guild
        
        member = interaction.user

        member_roles = set(member.roles)
        panel_roles = set([
            int(option.value)
            for option in select_menu.options
            if option.value.isdigit()
        ])
        selected_roles = set([
            int(role_id) 
            for role_id in values
            if role_id.isdigit()
        ])

        to_remove = (panel_roles & member_roles) - selected_roles

        try:
            await member.remove_roles(
                [
                    role
                    for r in to_remove
                    if (role := await self._get_role(guild, int(r))) is not None
                ],
                reason="Role Assignment",
                atomic=False
            )

            await member.add_roles(
                [
                    role
                    for r in selected_roles
                    if (role := await self._get_role(guild, int(r))) is not None
                ],
                reason="Role Assignment",
                atomic=False
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                f"**Error:** I do not have permission to manage roles. \nPlease make sure i have **Manage Roles** permission and my role is above the role you want me to manage.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Successfully updated your roles!"
            f"**Added:** {', '.join(f'<@&{role_id}>' for role_id in selected_roles)}"
            f"**Removed:** {', '.join(f'<@&{role_id}>' for role_id in to_remove)}",
            ephemeral=True
        )


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

        self._callbacks = RoleAssignmentCallbacks(self)

        self.message_ra_cache = TTLCache(maxsize=5000, ttl=300)
        # {
        #     "message_id": {"headers": "hi", "description": "roles!", "roles": [...], "config_version": 1}
        # }

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
            await interaction.response.send_message(
                f"## ⚠️ Error: Module Disabled"
                f"This module is disabled. Please run /modules to enable **{self.module_name}**"
            )
            return

        bot_perms = interaction.guild.me.guild_permissions
        if not bot_perms.manage_roles:
            await interaction.response.send_message(
                f"**Error:** Missing Permissions.\nPlease make sure i have **Manage Roles** permission.",
                ephemeral=True
            )
            return

        component_type = interaction.data["component_type"]

        if component_type == discord.ComponentType.button.value:
            await self._callbacks.on_button_callback(interaction)

        elif component_type == discord.ComponentType.button.value:
            await self._callbacks.on_select_menu_callback(interaction)

    
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