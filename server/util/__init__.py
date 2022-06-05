from .fs import TargetFileSystem
from .models import *
from fastapi.responses import JSONResponse
from .cfg import *

def err(code: int, reason: str = "Just because :)"):
    return JSONResponse(content={
        "result": "failure",
        "reason": reason
    }, status_code=code)

def suc(data: dict | list, code: int = 200):
    return JSONResponse(content={
        "result": "success",
        "value": data
    }, status_code=code)