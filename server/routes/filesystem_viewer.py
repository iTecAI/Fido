from starlette.status import *
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRouter
from util import TargetFileSystem, cfg, err, suc
import mimetypes

router = APIRouter(prefix="/files", tags=["files"])
fs = TargetFileSystem(**cfg()["target"])

__all__ = ["router"]

@router.get("/{sl_path:path}")
async def get_at(sl_path: str):
    print(sl_path)
    if fs.exists(sl_path):
        if fs.isdir(sl_path):
            items = fs.ls(sl_path)
            return suc({
                "path": sl_path,
                "items": [{
                    "path": str(i).rsplit("/", maxsplit=1)[1],
                    "is_directory": fs.isdir(sl_path + "/" + str(i).rsplit("/", maxsplit=1)[1])
                } for i in items]
            })
        else:
            def iterfile():
                with fs.open(sl_path, mode="rb") as f:
                    yield from f
            
            return StreamingResponse(iterfile(), media_type=mimetypes.guess_type(sl_path)[0])
    else:
        return err(HTTP_404_NOT_FOUND, "File not found")