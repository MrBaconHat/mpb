import traceback

import discord
from discord import ui, app_commands
from discord.ext import commands

from nestio.files import JSON


class ModulePagination(ui.LayoutView):
    def __init__(self, modules: list, module_config: dict, module_files: dict):
        self.modules = modules
        self.module_config = module_config
        self.module_files = module_files
        
        self.pages = []
        self.current_page = 0

        self.build_pages()

        self.container = ui.Container()
        self.container.add_item(self.pages[self.current_page])

        self.add_item(self.container)

    
    def build_pages(self):
        self.pages.clear()
        
        for cog in self.modules:
            container = ui.Container()

            config = self.module_config.get(cog.INTERNAL_NAME, {})
            is_enabled = config.get("is_enabled", False)
            module_toggle_button = ui.Button(
                label="Enable" if not is_enabled else "Disable",
                custom_id=f"toggle:{cog.INTERNAL_NAME}"
            )
            module_toggle_button.callback = self.toggle_button_callback

            toggle_section = ui.Section(
                f"{cog.MODULE_NAME}",
                accessory=ui.ActionRow(module_toggle_button)
            )

            container.add_item(toggle_section)

            self.pages.append(container)
    
    def update_page(self):
        self.container.clear_items()
        self.container.add_item(
            self.pages[self.current_page]
        )
    
    async def toggle_button_callback(self, interaction: discord.Interaction):
        custom_id = self.custom_id
        module_name = custom_id.split(":")[1]

        config = self.module_files[module_name]

        await config.set(
            "is_enabled", not await config.get("is_enabled", False)
        )

        self.module_config[module_name] = await config.get() or {}

        self.build_pages()
        self.update_page()

        await interaction.response.edit_message(view=self)
        

class Module(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.storage = bot.storage


    @app_commands.command(
        name="modules",
        description="Lists all the modules bot has to offer."
    )
    @app_commands.guild_only()
    async def modules(
        self, 
        i: discord.Interaction
    ):
        await i.response.defer(ephemeral=True)
        
        module = []
        module_config = {}
        module_files = {}
        
        for name, cog in self.bot.cogs.items():
            if not hasattr(cog, "INTERNAL_NAME"):
                continue

            module.append(cog)

        for cog in module:
            config = self.storage.get_module(i.guild.id, cog.INTERNAL_NAME, "config")

            module_config[cog.INTERNAL_NAME] = await config.get() or {}
            module_files[cog.INTERNAL_NAME] = config

        view = ModulePagination(
            module, 
            module_config,
            module_files
        )
        await i.followup.send(view=view, ephemeral=True)


    @modules.error
    async def on_error(self, interaction, error):
        traceback.print_exception(
            type(error), error, error.__traceback__
        )
        

async def setup(bot: commands.Bot):
    await bot.add_cog(Module(bot))