from .podcast_router import router as PodcastRouter

routers = [
    PodcastRouter
]

__all__ = ["routers"]