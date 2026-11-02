import aiosqlite
import traceback
from cachetools import TTLCache

import discord
from discord import ui, app_commands
from discord.ext import commands



class Module(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        module_name: str,
        module_description: str,
        internal_name: str,
        config_table: str,
        state_table: str
    ):
        self.bot = bot
        self.db = self.bot.db

        self.MODULE_NAME = module_name
        self.MODULE_DESCRIPTION = module_description
        self.INTERNAL_NAME = internal_name

        self.CONFIG_TABLE = config_table
        self.STATE_TABLE = state_table

        self.__enabled_cache = TTLCache(maxsize=5000, ttl=300)

    async def build_config_page(
        self,
        guild_id: str | int,
        parent_view
    ) -> list[ui.Item]:
        return []

    # ==============================
    # Module Management
    # ==============================

    async def is_enabled(self, guild_id: int) -> bool:
        key = (guild_id, self.INTERNAL_NAME)
        if key in self.__enabled_cache:
            return self.__enabled_cache[key]
            
        row = await self.db.fetchrow(
            """
            SELECT is_enabled
            FROM modules
            WHERE guild_id = ?
              AND module_name = ?
            """,
            (guild_id, self.INTERNAL_NAME)
        )

        enabled = bool(row["is_enabled"]) if row else False
        self.__enabled_cache[key] = enabled
        return enabled

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
        
        key = (guild_id, self.INTERNAL_NAME)
        self._enabled_cache[key] = enabled
        return enabled

    async def toggle(self, guild_id: int) -> bool:
        enabled = not await self.is_enabled(guild_id)
        return await self.set_enabled(guild_id, enabled)

    # ==============================
    # Private Database Helpers
    # ==============================

    async def _get_record(
        self,
        table: str,
        guild_id: int,
        where: dict | None = None
    ) -> aiosqlite.Row | None:
        conditions = ["guild_id = ?"]
        values = [guild_id]

        if where:
            conditions.extend(
                f"{column} = ?" for column in where
            )
            values.extend(where.values())

        return await self.db.fetchrow(
            f"""
            SELECT *
            FROM {table}
            WHERE {" AND ".join(conditions)}
            """,
            tuple(values)
        )

    async def _get_records(
        self,
        table: str,
        guild_id: int,
        where: dict | None = None
    ) -> list[aiosqlite.Row] | None:
        conditions = ["guild_id = ?"]
        values = [guild_id]

        if where:
            conditions.extend(
                f"{column} = ?" for column in where
            )
            values.extend(where.values())

        return await self.db.fetch(
            f"""
            SELECT *
            FROM {table}
            WHERE {" AND ".join(conditions)}
            """,
            tuple(values)
        )

    async def _insert_record(
        self,
        table: str,
        guild_id: int,
        **kwargs
    ):
        columns = ["guild_id", *kwargs.keys()]
        placeholders = ", ".join("?" for _ in columns)

        values = (guild_id, *kwargs.values())

        await self.db.execute(
            f"""
            INSERT INTO {table} (
                {", ".join(columns)}
            )
            VALUES ({placeholders})
            """,
            values
        )

        await self.db.commit()

    async def _update_record(
        self,
        table: str,
        guild_id: int,
        where: dict | None = None,
        **kwargs
    ):
        if not kwargs:
            return

        set_values = ", ".join(
            f"{column} = ?" for column in kwargs
        )

        conditions = ["guild_id = ?"]
        conditions.extend(
            f"{column} = ?" for column in (where or {})
        )

        values = (
            *kwargs.values(),
            guild_id,
            *((where or {}).values())
        )

        await self.db.execute(
            f"""
            UPDATE {table}
            SET {set_values}
            WHERE {" AND ".join(conditions)}
            """,
            values
        )

        await self.db.commit()

    async def _delete_record(
        self,
        table: str,
        guild_id: int,
        where: dict | None = None
    ):
        conditions = ["guild_id = ?"]
        values = [guild_id]

        if where:
            conditions.extend(
                f"{column} = ?" for column in where
            )
            values.extend(where.values())

        await self.db.execute(
            f"""
            DELETE FROM {table}
            WHERE {" AND ".join(conditions)}
            """,
            tuple(values)
        )

        await self.db.commit()

    # ==============================
    # Configuration
    # ==============================

    async def get_config(
        self,
        guild_id: int,
        where: dict | None = None
    ) -> aiosqlite.Row | None:
        return await self._get_record(
            self.CONFIG_TABLE,
            guild_id,
            where
        )

    async def get_configs(
        self,
        guild_id: int,
        where: dict | None = None
    ) -> list[aiosqlite.Row]:
        return await self._get_records(
            self.CONFIG_TABLE,
            guild_id,
            where
        )

    async def insert_config(
        self,
        guild_id: int,
        **kwargs
    ):
        await self._insert_record(
            self.CONFIG_TABLE,
            guild_id,
            **kwargs
        )

    async def update_config(
        self,
        guild_id: int,
        where: dict | None = None,
        **kwargs
    ):
        await self._update_record(
            self.CONFIG_TABLE,
            guild_id,
            where,
            **kwargs
        )

    async def delete_config(
        self,
        guild_id: int,
        where: dict | None = None
    ):
        await self._delete_record(
            self.CONFIG_TABLE,
            guild_id,
            where
        )

    # ==============================
    # State
    # ==============================

    async def get_state(
        self,
        guild_id: int,
        where: dict | None = None
    ) -> aiosqlite.Row | None:
        return await self._get_record(
            self.STATE_TABLE,
            guild_id,
            where
        )

    async def get_states(
        self,
        guild_id: int,
        where: dict | None = None
    ) -> list[aiosqlite.Row]:
        return await self._get_records(
            self.STATE_TABLE,
            guild_id,
            where
        )

    async def insert_state(
        self,
        guild_id: int,
        **kwargs
    ):
        await self._insert_record(
            self.STATE_TABLE,
            guild_id,
            **kwargs
        )

    async def update_state(
        self,
        guild_id: int,
        where: dict | None = None,
        **kwargs
    ):
        await self._update_record(
            self.STATE_TABLE,
            guild_id,
            where,
            **kwargs
        )

    async def delete_state(
        self,
        guild_id: int,
        where: dict | None = None
    ):
        await self._delete_record(
            self.STATE_TABLE,
            guild_id,
            where
        )


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
        
        # Buttons or select menus disabled by toggle button
        self.disabled_interactables: dict[str, list[ui.Item]] = {}
        self.selected_page = None

        self.TOGGLE_ON = "<:t_on:1566847934278926478>"
        self.TOGGLE_OFF = "<:t_off:1566847920228007937>"

        self.page_size = 22
        self.min = 0
        self.max = self.page_size  # Account for < and >


    def _iter_interactables(self, items: list[ui.Item]):
        """helper to recursively itwrate through ActionRow and find enabled interactables(buttons, select menus)"""
        for item in items:
            # if it's an ActionRow or container holding children, yield from them
            if hasattr(item, "children") and item.children:
                yield from self._iter_interactables(item.children)
            elif hasattr(item, "disabled"):
                yield item
                
            # Check if its a Section with a button
            if hasattr(item, "accessory") and item.accessory is not None:
                if hasattr(item.accessory, "disabled"):
                    yield item.accessory

    
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
            emoji=self.TOGGLE_OFF if not is_enabled else self.TOGGLE_ON,
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

        module_data = self.modules.get(self.selected_page, {})
        module = module_data.get("module")
        is_enabled = module_data.get("is_enabled", False)

        if module:
            container.add_item(
                self.build_toggle_button(module)
            )

        container.add_item(ui.Separator())

        if self.selected_page:
            page_items = self.pages[self.selected_page]
            if self.selected_page not in self.disabled_interactables: 
                self.disabled_interactables[self.selected_page] = set()
                
            for item in self._iter_interactables(page_items):
                if not is_enabled:
                    if not item.disabled:
                        self.disabled_interactables[self.selected_page].add(item)
                        item.disabled = True
                else:
                    if item in self.disabled_interactables[self.selected_page]:
                        item.disabled = False

            # Add everything into container at the end
            for item in page_items:
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