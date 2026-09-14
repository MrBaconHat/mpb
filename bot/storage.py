from nestio.files import JSON
from cachetools import TTLCache


class Storage:
    def __init__(self):
        self.guild_modules: dict[str, dict[str, JSON]] = TTLCache(maxsize=10000, ttl=3600)

    def get_module(
        self,
        guild_id: int | str,
        module: str
    ) -> JSON:
        guild_id = str(guild_id)
        
        guild = self.guild_modules.get(str(guild_id))

        if guild is None:
            guild = {}
            self.guild_modules[str(guild_id)] = guild

        if module not in guild:
            guild[module] = JSON(f"data/{guild_id}/{module}")

        return guild[module]