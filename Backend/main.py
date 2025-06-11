from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import releases, users, collections, recommendations
import traceback
import logging

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
