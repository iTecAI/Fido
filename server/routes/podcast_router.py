import mimetypes
from typing import List
from xmlrpc.client import boolean
from fastapi import Query, Request, Response
from fastapi.routing import APIRouter
from more_itertools import unzip
from util import Podcast, PodcastEpisode, cfg, TargetFileSystem, err, suc
import podcastindex
import tinydb
from tinydb import where
from requests.exceptions import *
from starlette.status import *
import string

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
        return suc({"save_id": cast.__uuid__, "feed": cast.to_dict_clean()})
    else:
        return err(HTTP_404_NOT_FOUND, f"Failed to locate feed with id {id}")


@router.delete("/saved/feeds/{uuid}")
async def delete_saved_feed(uuid: str):
    removed = table.remove(where("__uuid__") == uuid)
    return suc({"removed": len(removed)})

@router.post("/saved/feeds/{uuid}/fetch")
async def set_fetch_mode(uuid: str, f: boolean):
    r = table.update({"autofetch": f}, where("__uuid__") == uuid)
    if len(r) > 0:
        return suc(Podcast.from_db(table, where("__uuid__") == uuid).to_dict_clean())
    else:
        return err(HTTP_404_NOT_FOUND, reason=f"Saved podcast with UUID {uuid} not found.")


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


@router.get("/episodes/{id}")
async def get_episodes_by_feed_id(id: str):
    try:
        raw_data = index.episodesByFeedId(id, max_results=10000)
    except HTTPError:
        return err(HTTP_400_BAD_REQUEST, "Failed to get episodes from Index API")
    except ReadTimeout:
        return err(HTTP_408_REQUEST_TIMEOUT, "Request to Index API timed out")

    eps = [PodcastEpisode.from_api_item(e) for e in raw_data["items"]]
    return suc({i.id: i.to_dict_clean() for i in eps})


@router.get("/download/feed/{id}")
async def download_feed(
    request: Request, id: str, n: List[int | str] = Query([]), folder: str = None
):
    try:
        episodes: list[PodcastEpisode] = [
            PodcastEpisode.from_api_item(e)
            for e in index.episodesByFeedId(id, max_results=10000)["items"]
        ]
    except HTTPError:
        return err(HTTP_400_BAD_REQUEST, "Failed to get episodes from Index API")
    except ReadTimeout:
        return err(HTTP_408_REQUEST_TIMEOUT, "Request to Index API timed out")
    if n and len(n) > 0:
        episodes = [
            e
            for e in episodes
            if e.episodeNumber in n or e.episodeNumber == None and "null" in n
        ]

    if not folder:
        try:
            raw_data = index.podcastByFeedId(id)
        except HTTPError:
            return err(HTTP_400_BAD_REQUEST, "Failed to get feed from Index API")
        except ReadTimeout:
            return err(HTTP_408_REQUEST_TIMEOUT, "Request to Index API timed out")

        if not raw_data["feed"]:
            return err(HTTP_404_NOT_FOUND, f"Failed to locate feed with id {id}")

        feed = Podcast.from_feed(raw_data["feed"])
        folder = [
            (
                i
                if i in string.ascii_letters
                or i in string.digits
                or i in "_ (){}[]+-,:;<>=#&!$%"
                else "-"
            )
            for i in feed.title
        ].join("")
    names, resources = unzip(
        [(e.title + str(mimetypes.guess_extension(e.contentType)), e) for e in episodes]
    )

    downloads = fs.download(
        folder,
        resources=list(resources),
        names=[
            [
                (
                    i
                    if i in string.ascii_letters
                    or i in string.digits
                    or i in "_ (){}[]+-,:;<>=#&!$%"
                    else "-"
                )
                for i in n
            ].join("")
            for n in names
        ],
    )
    return downloads
