import traceback

import discord
from discord import ui, app_commands
from discord.ext import commands


class Module(commands.Cog):
    def __init__(
        self, 
        bot: commands.Bot,
            
        module_name: str, 
        module_description: str, 
        internal_name: str
    ):
        self.bot = bot
        self.db = self.bot.db

        self.MODULE_NAME = module_name
        self.MODULE_DESCRIPTION = module_description
        self.INTERNAL_NAME = internal_name

    
    async def build_config_page(
        self,
        guild_id: str | int,
        parent_view
    ) -> list[ui.Item]:
        return []


    async def is_enabled(
        self,
        guild_id: int
    ) -> bool:
        row = await self.db.fetchrow(
            """
            SELECT is_enabled
            FROM modules
            WHERE guild_id = ?
              AND module_name = ?
            """,
            (guild_id, self.INTERNAL_NAME)
        )
        if row is None:
            return False

        return bool(row["is_enabled"])

    async def set_enabled(
        self,
        guild_id: int,
        enabled: bool
    ) -> bool:
        await self.db.execute(
            """
            INSERT INTO modules (
                guild_id,
                module_name,
                is_enabled
            )
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, module_name)
            DO UPDATE SET is_enabled = excluded.is_enabled
            """,
            (guild_id, self.INTERNAL_NAME, enabled)
        )
        await self.db.commit()

        return enabled

    async def toggle(
        self,
        guild_id: int
    ) -> bool:
        enabled = await self.is_enabled(guild_id)

        await self.set_enabled(
            guild_id,
            not enabled
        )

        return not enabled


class ModuleView(ui.LayoutView):
    def __init__(
        self,
        guild_id: int,
        modules: dict,
    ):
        super().__init__()

        self.guild_id = guild_id
        self.modules = modules
        
        self.pages: dict[str, list[ui.Item]] = {}
        self.selected_page = None

        self.page_size = 22
        self.min = 0
        self.max = self.page_size  # Account for < and >

    
    async def initialize(self):
        await self.build_pages()
        await self.render_page()


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

        modules = [
            data["module"]
            for data in self.modules.values()
        ]

        for module in modules[self.min:self.max]:
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

    def build_toggle_button(self, module: Module):
        config = self.modules.get(module.INTERNAL_NAME, {})
        
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

        return toggle_section
    

    async def build_pages(self):
        self.pages.clear()
        
        for data in self.modules.values():
            module = data["module"]
            
            components: list[ui.Item] = []

            module_components = await module.build_config_page(
                self.guild_id,
                self
            )
            
            for ui_item in module_components:
                components.append(ui_item)

            self.pages[module.INTERNAL_NAME] = components

    
    async def update_module_page(self, view: ui.LayoutView):
        items = []

        for child in view.children:
            if isinstance(child, ui.Container):
                items.extend(child.children)

        self.pages[self.selected_page] = items
        await self.render_page()

    
    async def render_page(self):
        self.clear_items()

        container = ui.Container()

        container.add_item(
            ui.ActionRow(self.build_select_menu())
        )

        module = self.modules[self.selected_page]["module"]

        if module:
            container.add_item(
                self.build_toggle_button(module)
            )

        container.add_item(ui.Separator())

        if self.selected_page:
            for item in self.pages[self.selected_page]:
                container.add_item(item)

        self.add_item(container)

    
    async def toggle_button_callback(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]
        module_name = custom_id.split(":")[1]

        module = self.modules[module_name]["module"]
            
        enabled = await module.toggle(self.guild_id)

        self.modules[module_name]["is_enabled"] = enabled

        await self.render_page()

        await interaction.response.edit_message(view=self)

    async def select_menu_callback(self, interaction: discord.Interaction):
        value = interaction.data["values"][0]

        if value == "back":
            self.min -= self.page_size
            self.max -= self.page_size

        elif value == "forward":
            self.min += self.page_size
            self.max += self.page_size

        else:
            self.selected_page = value

        await self.render_page()

        await interaction.response.edit_message(view=self)
        

class ModuleManagement(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


    @app_commands.command(
        name="modules",
        description="Lists all the modules bot has to offer."
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def modules(
        self, 
        i: discord.Interaction
    ):
        await i.response.defer(ephemeral=True)
        
        module = {}
        
        for name, cog in self.bot.cogs.items():
            if not hasattr(cog, "INTERNAL_NAME"):
                continue

            module[cog.INTERNAL_NAME] = {
                "module": cog,
                "is_enabled": await cog.is_enabled(i.guild.id)
            }

        view = ModuleView(
            i.guild.id,
            module
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