import httpx
import json
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

async def fetch_release_from_discogs(release_id: int):
    """Fetch release data from Discogs API and parse required fields"""
    # Add authentication parameters
    params = {
        "key": settings.DISCOGS_API_KEY,
        "secret": settings.DISCOGS_API_SECRET
    }
    
    logger.info(f"Discogs API request: GET /releases/{release_id}")
    logger.debug(f"Request params: {params}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.discogs.com/releases/{release_id}",
                headers={
                    "User-Agent": "Spinly/1.0",
                    "Accept": "application/json"
                },
                params=params,
                timeout=30.0  # Increase timeout to 30 seconds
            )
            
            logger.info(f"Discogs API response status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"Discogs API returned status code {response.status_code}")
                logger.error(f"Response: {response.text}")
                raise Exception(f"Discogs API error: {response.status_code} - {response.text}")
                
            try:
                data = response.json()
                logger.debug("Successfully parsed JSON response from Discogs API")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response text: {response.text[:500]}...")
                raise Exception(f"Invalid JSON response from Discogs API: {str(e)}")
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        raise Exception(f"Failed to connect to Discogs API: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

    # Log the full response for debugging
    logger.debug(f"Full Discogs API response: {json.dumps(data, indent=2)[:500]}...")
    
    # Extract data safely with better error handling
    try:
        artist_name = "Unknown Artist"
        if data.get("artists") and isinstance(data["artists"], list) and len(data["artists"]) > 0:
            artist_name = data["artists"][0].get("name", "Unknown Artist")
        
        label_name = None
        if data.get("labels") and isinstance(data["labels"], list) and len(data["labels"]) > 0:
            label_name = data["labels"][0].get("name")
        
        year_value = None
        if data.get("year"):
            try:
                year_value = int(data["year"])
            except (ValueError, TypeError):
                year_value = None
        
        styles_list = []
        if data.get("styles") and isinstance(data["styles"], list):
            styles_list = data["styles"]
        
        processed_data = {
            "id": release_id,
            "title": data.get("title", "Unknown Title"),
            "artist": artist_name,
            "year": year_value,
            "label": label_name,
            "styles": styles_list
        }
        
        logger.debug(f"Processed data: {processed_data}")
        return processed_data
    except Exception as e:
        logger.error(f"Error processing Discogs data: {e}")
        # Return minimal data to avoid crashing
        return {
            "id": release_id,
            "title": data.get("title", "Unknown Title"),
            "artist": "Unknown Artist",
            "year": None,
            "label": None,
            "styles": []
        }