from pathlib import Path

from nestio.files import JSON
from cachetools import TTLCache


class Storage:
    
    def get_module(
        self,
        guild_id: int | str,
        module: str,
        type: str
    ) -> JSON:
        return JSON(f"data/{guild_id}/{module}/{type}.json")

    async def is_enabled(
        self, 
        guild_id: str | int, 
        module: str
    ) -> bool:
        directory = Path(f"data/{guild_id}/{module}")
        if not directory.is_dir():
            return False

        json = JSON(f"data/{guild_id}/{module}/config.json")
        config_data = await json.get()

        return config_data.get("is_enabled", False)