from .podcast_router import router as PodcastRouter
from .filesystem_viewer import router as FSRouter

routers = [
    PodcastRouter,
    FSRouter
]

__all__ = ["routers"]