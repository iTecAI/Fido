from fastapi import Response
from fastapi.routing import APIRouter
from util import Podcast, cfg, TargetFileSystem, err, suc
import podcastindex
import tinydb
from tinydb import where
from requests.exceptions import *
from starlette.status import *

__all__ = ["router"]

router = APIRouter(prefix="/podcasts", tags=["podcasts"])
index = podcastindex.init(cfg()["modules"]["podcasts"]["key"])
fs = TargetFileSystem(**cfg()["target"])
table = tinydb.TinyDB(cfg()["db"]).table(cfg()["modules"]["podcasts"]["table"])

@router.get("/search")
async def search_by_term(query: str, clean: bool | None = False):
    try:
        raw_data = index.search(query, clean=clean)
    except HTTPError:
        return err(HTTP_400_BAD_REQUEST, "Failed to get feeds from Index API")
    except ReadTimeout:
        return err(HTTP_408_REQUEST_TIMEOUT, "Request to Index API timed out")
    casts = {f["id"]: Podcast.from_feed(f).to_dict_clean() for f in raw_data["feeds"]}
    return suc(casts)

@router.put("/saved/feeds/{id}")
async def save_feed(id: int):
    try:
        raw_data = index.podcastByFeedId(id)
    except HTTPError:
        return err(HTTP_400_BAD_REQUEST, "Failed to get feed from Index API")
    except ReadTimeout:
        return err(HTTP_408_REQUEST_TIMEOUT, "Request to Index API timed out")
    
    if raw_data["feed"]:
        cast = Podcast.from_feed(raw_data["feed"])
        cast.save(table)
        return suc({
            "save_id": cast.__uuid__,
            "feed": cast.to_dict_clean()
        })
    else:
        return err(HTTP_404_NOT_FOUND, f"Failed to locate feed with id {id}")

@router.delete("/saved/feeds/{uuid}")
async def delete_saved_feed(uuid: str):
    removed = table.remove(where("__uuid__") == uuid)
    return suc({
        "removed": len(removed)
    })

@router.get("/saved/feeds")
async def get_saved_feeds():
    casts = [Podcast.from_raw(c) for c in table.all()]
    return suc({cast.__uuid__: cast.to_dict_clean() for cast in casts})

@router.get("/saved/feeds/{uuid}")
async def get_saved_feeds(uuid: str):
    cast = Podcast.from_db(table, where("__uuid__") == uuid)
    if cast:
        return suc(cast.to_dict_clean())
    else:
        return err(HTTP_404_NOT_FOUND, f"Failed to locate saved podcast {uuid}")

