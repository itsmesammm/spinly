import os
from pydantic_settings import BaseSettings, SettingsConfigDict

# Calculate the absolute path to the .env file. This is the robust way.
# It finds this file's location and navigates up to the project root.
_config_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.dirname(os.path.dirname(_config_dir))
_project_root = os.path.dirname(_backend_dir)
_dotenv_path = os.path.join(_project_root, '.env')



class Settings(BaseSettings):
    DATABASE_URL: str
    DISCOGS_API_KEY: str
    DISCOGS_API_SECRET: str

    # JWT settings
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Use Pydantic's own mechanism to load the .env file using the absolute path.
    model_config = SettingsConfigDict(
        env_file=_dotenv_path,
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()
