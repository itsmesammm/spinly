from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import releases, users, collections


# Create the app instance
app = FastAPI(title="Spinly API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(users.router, prefix="/api", tags=["users"])
app.include_router(collections.router, prefix="/api", tags=["collections"])
app.include_router(releases.router, prefix="/api", tags=["releases"])

@app.get("/")
async def root():
    return {"message": "Welcome to Spinly API"}
