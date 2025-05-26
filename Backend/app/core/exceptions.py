from fastapi import HTTPException
from typing import Any, Dict, Optional

class SpinlyException(HTTPException):
    """Base exception for Spinly API"""
    def __init__(
        self,
        status_code: int,
        detail: str,
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)

class NotFoundException(SpinlyException):
    """Resource not found"""
    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            status_code=404,
            detail=f"{resource} with id {resource_id} not found"
        )

class DuplicateError(SpinlyException):
    """Resource already exists"""
    def __init__(self, field: str, value: str):
        super().__init__(
            status_code=400,
            detail=f"{field} '{value}' already exists"
        )

class UnauthorizedError(SpinlyException):
    """User is not authorized"""
    def __init__(self, message: str = "Not authorized"):
        super().__init__(
            status_code=401,
            detail=message,
            headers={"WWW-Authenticate": "Bearer"}
        )
