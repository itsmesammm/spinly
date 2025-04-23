from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str  # This will store the database connection URL

    class Config:
        env_file = ".env"  # It tells Pydantic to load values from `.env` file

settings = Settings()  # Creates an instance of Settings, so we can use `settings.DATABASE_URL`
