import traceback

import discord
from discord import ui, app_commands
from discord.ext import commands

from nestio.files import JSON


class Module(commands.Cog):
    def __init__(self, module_name: str, module_description: str, internal_name: str):
        self.MODULE_NAME = module_name
        self.MODULE_DESCRIPTION = module_description
        self.INTERNAL_NAME = internal_name

    
    async def build_config_page(
        self,
        guild_id: str | int
    ) -> list[ui.Item] | None:
        return None        


class ModuleView(ui.LayoutView):
    def __init__(
        self,
        guild_id: int,
        modules: list, 
        module_config: dict, 
        module_files: dict
    ):
        super().__init__()

        self.guild_id = guild_id
        self.modules = modules
        self.module_config = module_config
        self.module_files = module_files
        
        self.pages: dict[str, list[ui.Item]] = {}
        self.selected_page = None

        self.min = 0
        self.max = 22  # Account for < and >

    
    async def initialize(self):
        await self.build_pages()

        container = ui.Container()

        container.add_item(
            ui.ActionRow(
                self.build_select_menu()
            )
        )

        if self.selected_page:
            for item in self.pages[self.selected_page]:
                container.add_item(item)

        self.add_item(container)


    def build_select_menu(self) -> ui.Select:
        options = []

        if self.min > 0:
            options.append(
                discord.SelectOption(
                    label="<",
                    description="Previous",
                    value="back"
                )
            )

        if self.selected_page is None and len(self.pages) > 0:
            self.selected_page = list(self.pages)[0]

        for module in self.modules[self.min:self.max]:
            options.append(
               discord.SelectOption(
                   label=module.MODULE_NAME,
                   description=module.MODULE_DESCRIPTION,
                   value=module.INTERNAL_NAME,
                   default=module.INTERNAL_NAME == self.selected_page
                )
            )

        if self.max < len(self.modules):
            options.append(
                discord.SelectOption(
                    label=">",
                    description="Forward",
                    value="forward"
                )
            )
            
        select = ui.Select(
            placeholder="Select a module...",
            options=options
        )
        select.callback = self.select_menu_callback
        
        return select
    

    async def build_pages(self):
        self.pages.clear()
        
        for module in self.modules:
            components: list[ui.Item] = []

            config = self.module_config.get(module.INTERNAL_NAME, {})

            is_enabled = config.get("is_enabled", False)
            module_toggle_button = ui.Button(
                emoji="<:toggle_off:1552010483710689391>" if not is_enabled else "<:toggle_on:1552010109285175356>",
                custom_id=f"toggle:{module.INTERNAL_NAME}"
            )
            module_toggle_button.callback = self.toggle_button_callback

            toggle_section = ui.Section(
                f"### {module.MODULE_NAME}\n-# {getattr(module, 'MODULE_DESCRIPTION', 'No description')}",
                accessory=module_toggle_button
            )

            components.append(toggle_section)
            components.append(ui.Separator())

            module_components = await module.build_config_page(self.guild_id) or []
            for ui_item in module_components:
                components.append(ui_item)

            self.pages[module.INTERNAL_NAME] = components

    async def update_page(self):
        self.clear_items()
        await self.initialize()   
    
    async def toggle_button_callback(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]
        module_name = custom_id.split(":")[1]

        config = self.module_files[module_name]

        await config.set(
            "is_enabled", not await config.get("is_enabled", False)
        )

        self.module_config[module_name] = await config.get() or {}

        await self.build_pages()
        await self.update_page()

        await interaction.response.edit_message(view=self)

    async def select_menu_callback(self, interaction: discord.Interaction):
        print("select callback")
        value = interaction.data["values"][0]
        print("value:", value)

        if value == "back":
            self.min -= 22
            self.max -= 22

        elif value == "forward":
            self.min += 22
            self.max += 22

        else:
            self.selected_page = value

        await self.build_pages()
        await self.update_page()

        await interaction.response.edit_message(view=self)
        

class ModuleManagement(commands.Cog):
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

        view = ModuleView(
            i.guild.id,
            module, 
            module_config,
            module_files
        )
        await view.initialize()
        
        await i.followup.send(view=view, ephemeral=True)


    @modules.error
    async def on_error(self, interaction, error):
        traceback.print_exception(
            type(error), error, error.__traceback__
        )
        

async def setup(bot: commands.Bot):
    await bot.add_cog(ModuleManagement(bot))