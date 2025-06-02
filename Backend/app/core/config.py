from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    DISCOGS_API_KEY: str
    DISCOGS_API_SECRET: str

    class Config:
        env_file = ".env"  # It tells Pydantic to load values from `.env` file


settings = Settings()  # Creates an instance of Settings, so we can use `settings.DATABASE_URL`

print("🚀 Loaded DATABASE_URL:", settings.DATABASE_URL)


