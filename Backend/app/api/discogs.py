import httpx

async def fetch_release_from_discogs(release_id: int):
    """Basic Discogs API fetcher"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.discogs.com/releases/{release_id}",
            headers={"User-Agent": "Spinly/1.0"}
        )
    return {
        "id": release_id,
        "title": response.json().get("title"),
        "artist": response.json()["artists"][0]["name"]
    }