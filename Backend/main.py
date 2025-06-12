from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import releases, users, collections, recommendations
import traceback
import logging
import uvicorn # For running programmatically
from dotenv import load_dotenv # For loading .env file
import os # For path manipulation

# Explicitly load .env file from the project root (one directory up from Backend/)
# This ensures .env is found whether running from root or Backend/ directly.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, ".env"))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

# Create the app instance with debug mode enabled
app = FastAPI(title="Spinly API", debug=True)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add exception handler for detailed error responses
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_detail = traceback.format_exc()
    logger.error(f"Unhandled exception: {str(exc)}\n{error_detail}")
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "detail": error_detail,
            "path": request.url.path
        }
    )

# Include routes
app.include_router(users.router, prefix="/api", tags=["users"])
app.include_router(collections.router, prefix="/api", tags=["collections"])
app.include_router(releases.router, prefix="/api", tags=["releases"])
app.include_router(recommendations.router, prefix="/api", tags=["Recommendations"])


@app.get("/")
async def root():
    return {"message": "Welcome to Spinly API"}


if __name__ == "__main__":
    # This block runs when the script is executed directly (e.g., python Backend/main.py or by clicking 'Run' in an IDE)
    # It will use the host and port defaults for uvicorn (127.0.0.1:8000)
    # The --reload flag is not used here as IDEs often handle reloading separately.
    # If you need reload when running this way, you can add reload=True to uvicorn.run()
    uvicorn.run("main:app", host="127.0.0.1", port=8000, log_level="info")
