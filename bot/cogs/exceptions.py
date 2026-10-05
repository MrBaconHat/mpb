import traceback

import discord
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


async def setup(bot: commands.Bot):
    await bot.add_cog(Exception(bot))