from app.api import releases
from fastapi import FastAPI

# Create the app instance
app = FastAPI()

# Include routes
app.include_router(releases.router, prefix="/api")

