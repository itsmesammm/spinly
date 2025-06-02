import httpx

async def fetch_release_from_discogs(release_id: int):
    """Fetch release data from Discogs API and parse required fields"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.discogs.com/releases/{release_id}",
            headers={"User-Agent": "Spinly/1.0"}
        )
        data = response.json()

    return {
        "id": release_id,
        "title": data.get("title", "Unknown Title"),
        "artist": data["artists"][0]["name"] if data.get("artists") else "Unknown Artist",
        "year": int(data.get("year", 0)) if data.get("year") else None,
        "label": data["labels"][0]["name"] if data.get("labels") else None,
        "styles": data.get("styles", [])  # Get all styles as a list
    }