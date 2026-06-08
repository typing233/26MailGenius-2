from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


class AppException(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: list | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []


class ConflictError(AppException):
    def __init__(self, message: str = "Resource conflict"):
        super().__init__("CONFLICT", message, status_code=409)


class InvalidStateError(AppException):
    def __init__(self, message: str = "Invalid state transition"):
        super().__init__("INVALID_STATE", message, status_code=422)


class InvalidTokenError(AppException):
    def __init__(self, message: str = "Token is invalid or expired"):
        super().__init__("INVALID_TOKEN", message, status_code=400)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": str(exc),
                "details": [],
            }
        },
    )
