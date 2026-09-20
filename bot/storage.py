from pathlib import Path

from nestio.files import JSON
from cachetools import TTLCache


class Storage:
    def __init__(self):
        self.guild_modules: dict[str, dict[str, JSON]] = TTLCache(maxsize=10000, ttl=3600)

    def get_module(
        self,
        guild_id: int | str,
        module: str,
        type: str
    ) -> JSON:
        guild_id = str(guild_id)
        
        guild = self.guild_modules.get(str(guild_id))

        if guild is None:
            guild = {}
            self.guild_modules[str(guild_id)] = guild

        if module not in guild:
            guild[module] = JSON(f"data/{guild_id}/{module}/{type}.json")

        return guild[module]

    async def is_enabled(
        self, 
        guild_id: str | int, 
        module: str
    ) -> bool:
        directory = Path(f"data/{guild_id}/{module}")
        if not directory.is_dir:
            return False

        json = JSON(f"data/{guild_id}/{module}/config.json")
        config_data = await json.get()

        return config_data.get("is_enabled", False)