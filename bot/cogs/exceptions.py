import traceback

import discord
from discord import app_commands
from discord.ext import commands


class Exception(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        traceback.print_exception(
            type(error), error, error.__traceback__
        )

    @commands.Cog.listener()
    async def on_error(self, error):
        traceback.print_exception(
            type(error), error, error.__traceback__
        )

    @commands.Cog.listener()
    async def on_app_command_error(self, i: discord.Interaction, error):
        text = ""
        
        if isinstance(error, app_commands.MissingPermissions):
            missing_permissions = [
                mp.replace("_", " ")
                for mp in error.missing_permissions
            ]

            text = f"You're missing the following permissions: **{', '.join(missing_permissions)}**"


        if i.response.is_done():
            await i.followup.send(text, ephemeral=True)
            
        else:
            await i.response.send_message(text, ephemeral=True)
            

async def setup(bot: commands.Bot):
    await bot.add_cog(Exception(bot))