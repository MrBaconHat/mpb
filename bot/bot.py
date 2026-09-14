import discord
from discord.ext import commands

import os
import traceback

from colorama import Fore, Style, init
init(autoreset=True)

from nestio.env import Env
from nestio.files import JSON


class MyBot(commands.Bot):
    def __init__(self):
        
        intents = discord.Intents.all()

        self.servers_modules: dict[str, dict[str, JSON]] = {}
        
        super().__init__(command_prefix="/", intents=intents, help_command=None)


    async def setup_hook(self):
        servers = [
            srvr_dir
            for srvr_dir in os.listdir("data")
            if srvr_dir.isdigit()
        ]
        modules: dict[str, dict[str, JSON]] = {}
        for server in servers:
            module[server] = {}
            
            for module in os.listdir(f"data/{server}"):
                if module.endswith(".json"):
                    modules[server][module] = JSON(f"data/{server}/{module}")
        self.servers_modules = modules
            
        # === Cogs Loader ===
        cogs = [
            cog[:3]
            for cog in os.listdir("bot/cogs")
            if cog.endswith(".py") and not cog.startswith("__")
        ]
        for cog in cogs:
            try:
                await self.load_extension(f"bot.cogs.{cog}")
                print(
                    Fore.GREEN + Style.BRIGHT +
                    f"[+] Successfully loaded: {cog}"
                )
            except Exception as e:
                print(
                    Fore.RED + Style.BRIGHT +
                    f"[-] Failed to load: {cog}"
                )
                traceback.print_exception(
                    type(e), e, e.__traceback__
                )

    async def on_ready(self):
        print(
            Fore.GREEN + Style.BRIGHT +
            f"Successfully logged in as: {self.user.name} ({self.user.id})"
        )

    async def start_bot(self):
        token = Env().get("DISCORD_BOT_TOKEN", None)
        if token is None:
            print(
                Fore.RED + Style.BRIGHT +
                f"DISCORD_BOT_TOKEN should not be a NoneType."
            )
            return

        try:
            await self.start(token)
            
        except discord.LoginFailure as e:
            print(
                Fore.RED + Style.BRIGHT +
                f"Error logging in: {e}"
            )
            
        except Exception as e:
            print(
                Fore.RED + Style.BRIGHT +
                f"Unexpected error when starting the bot."
            )
            traceback.print_exception(
                type(e), e, e.__traceback__
            )


bot = MyBot()