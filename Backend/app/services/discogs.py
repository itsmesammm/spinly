from typing import Dict, Any
import httpx
import logging
from fastapi import Depends
from app.core.config import settings

logger = logging.getLogger(__name__)

class DiscogsService:
    def __init__(self):
        self.base_url = "https://api.discogs.com"
        self.headers = {
            "User-Agent": "SpinlyApp/1.0"}
        self.params = {
            "key": settings.DISCOGS_API_KEY,
            "secret": settings.DISCOGS_API_SECRET
        }

    async def get_release(self, release_id: int) -> Dict[str, Any]:
        """
        Gets a single release from Discogs by its ID and performs initial data parsing.
        This method combines the logic from the old get_release and fetch_release_from_discogs.
        """
        logger.info(f"DiscogsService: GET /releases/{release_id}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/releases/{release_id}",
                    headers=self.headers,
                    params=self.params,
                    timeout=30.0
            )
            response.raise_for_status() # Raises an exception for 4xx and 5xx responses

            # we return the full JSON data, the music_data_service will handle parsing
            return response.json()
        
        except httpx.RequestError as e:
            logger.error(f"Request error to DIscogs API: {e}")
            raise Exception(f"Faile to connect to Discogs API: {str(e)}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Discogs API returned status {e.response.status_code}: {e.response.text}")
            raise Exception(f"Discogs API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Unexpected error occurred in DiscogsService: {e}")
            raise

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

