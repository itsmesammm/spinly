from typing import Optional, Dict, Any
import httpx
from fastapi import Depends
from app.core.config import settings

class DiscogsService:
    def __init__(self):
        self.base_url = "https://api.discogs.com"
        self.headers = {
            "User-Agent": "SpinlyApp/1.0"
        }
        # Add consumer key and secret as parameters
        self.params = {
            "key": settings.DISCOGS_API_KEY,
            "secret": settings.DISCOGS_API_SECRET
        }

    async def get_release(self, release_id: str) -> Dict[str, Any]:
        """Get a release from Discogs"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/releases/{release_id}",
                headers=self.headers,
                params=self.params
            )
            response.raise_for_status()
            return response.json()

    async def search_releases(self, query: str, page: int = 1) -> Dict[str, Any]:
        """Search releases on Discogs"""
        search_params = {
            **self.params,
            "q": query,
            "type": "release",
            "page": page
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/database/search",
                params=search_params,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

# Dependency
async def get_discogs_service() -> DiscogsService:
    """Dependency injection for DiscogsService"""
    return DiscogsService()
