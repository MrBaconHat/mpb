import aiosqlite
from cachetools import TTLCache

import discord
from discord import ui
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
        self.__enabled_cache[key] = enabled
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