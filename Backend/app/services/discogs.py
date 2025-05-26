from typing import Optional, Dict, Any
import httpx
from fastapi import Depends

class DiscogsService:
    def __init__(self):
        self.base_url = "https://api.discogs.com"
        self.headers = {
            "User-Agent": "SpinlyApp/1.0",
        }

    async def get_release(self, release_id: str) -> Dict[str, Any]:
        """Get a release from Discogs"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/releases/{release_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def search_releases(self, query: str, page: int = 1) -> Dict[str, Any]:
        """Search releases on Discogs"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/database/search",
                params={"q": query, "type": "release", "page": page},
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

# Dependency
async def get_discogs_service() -> DiscogsService:
    """Dependency injection for DiscogsService"""
    return DiscogsService()
