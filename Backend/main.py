from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import releases, users, collections, recommendations, auth, jobs
import traceback
import logging
import uvicorn # For running programmatically
from dotenv import load_dotenv # For loading .env file
import os # For path manipulation



# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

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
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])


@app.get("/")
async def root():
    return {"message": "Welcome to Spinly API"}


if __name__ == "__main__":
    # This block runs when the script is executed directly (e.g., python Backend/main.py or by clicking 'Run' in an IDE)
    # For Render deployment, use 0.0.0.0 and PORT from environment
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
