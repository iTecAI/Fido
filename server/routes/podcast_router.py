from fastapi.routing import APIRouter
from util import Podcast, cfg, TargetFileSystem

__all__ = ["router"]

router = APIRouter(prefix="/podcasts", tags=["modules", "podcasts"])

