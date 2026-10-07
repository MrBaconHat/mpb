import aiosqlite


class Database:
    def __init__(self, path: str):
        self.path = path
        self.connection: aiosqlite.Connection = None

    async def initialize(self):
        await self.execute("""
        CREATE TABLE IF NOT EXISTS modules (
            guild_id INTEGER NOT NULL,
            module_name TEXT NOT NULL,
            is_enabled INTEGER NOT NULL DEFAULT 0,

            PRIMARY KEY (guild_id, module_name)
        )
    """)

        await self.commit()

    async def connect(self):
        self.connection = await aiosqlite.connect(self.path)
        
        self.connection.row_factory = aiosqlite.Row

    async def close(self):
        if self.connection:
            await self.connection.close()

    # ==== Methods ====
    async def execute(self, query: str, parameters: tuple = ()):
        await self.connection.execute(query, parameters)

    async def fetch(self, query: str, parameters: tuple = ()):
        cursor = await self.connection.execute(query, parameters)

        try:
            return await cursor.fetchall()
        finally:
            await cursor.close()

    async def fetchrow(self, query: str, parameters: tuple = ()):
        cursor = await self.connection.execute(query, parameters)

        try:
            return await cursor.fetchone()
        finally:
            await cursor.close()

    async def commit(self):
        await self.connection.commit()