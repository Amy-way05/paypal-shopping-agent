"""Error helper so every error matches API.md: {"detail": {"code", "message", ...}}."""
from fastapi import HTTPException


def api_error(status, code, message, **extra):
    return HTTPException(status_code=status, detail={"code": code, "message": message, **extra})
