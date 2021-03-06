from argparse import ArgumentError
from fsspec import AbstractFileSystem
import importlib

from more_itertools import unzip

from .models import Resource
from .cfg import cfg
from tinydb import TinyDB, where
from time import time
from hashlib import sha256
from threading import Thread


class TargetFileSystem:
    def __init__(
        self,
        module: str = "",
        subclass: str = "",
        args: list = [],
        kwargs: dict = {},
        root_path: str = "",
    ):
        self.module = module
        self.subclass = subclass
        self.args = args
        self.kwargs = kwargs
        self.root_path = root_path
        self.db = TinyDB(cfg()["db_downloads"])
        self.locked = False

        self.interface: AbstractFileSystem = getattr(
            importlib.import_module(f"fsspec.implementations.{self.module}"),
            self.subclass,
        )(*args, **kwargs)

    def wait_lock(self):
        while self.locked:
            pass

    def _path(self, path: str):
        return self.root_path.rstrip("/") + "/" + path

    def open(self, path: str, **kwargs):
        return self.interface.open(self._path(path), **kwargs)

    def walk(self, path: str, **kwargs):
        return self.interface.walk(self._path(path), **kwargs)

    def ls(self, path: str, **kwargs):
        return self.interface.ls(self._path(path), **kwargs)

    def makedirs(self, path: str, exist_ok=False):
        return self.interface.makedirs(self._path(path), exist_ok=exist_ok)
    
    def exists(self, path: str, **kwargs):
        return self.interface.exists(self._path(path), **kwargs)
    
    def isdir(self, path: str):
        return self.interface.isdir(self._path(path))

    def _handle_download(
        self,
        download: str,
        id: str,
        container: str,
        name: str,
        resource: Resource,
        args=[],
        kwargs={},
    ):
        self.wait_lock()
        self.locked = True
        self.db.update(
            {
                "type": "in_progress",
                "startedTimestamp": time(),
                "message": "Downloading...",
            },
            (where("download_id") == download) & (where("item_id") == id),
        )
        self.locked = False
        with self.open(
            f"{container}/{resource.download_pathprefix()}{name}", mode="wb"
        ) as f:
            success, result = resource.download(f, *args, **kwargs)

        if success:
            self.wait_lock()
            self.locked = True
            self.db.update(
                {"type": "complete", "completedTimestamp": time(), "message": result},
                (where("download_id") == download) & (where("item_id") == id),
            )
            self.locked = False
        else:
            self.wait_lock()
            self.locked = True
            self.db.update(
                {"type": "error", "completedTimestamp": time(), "message": result},
                (where("download_id") == download) & (where("item_id") == id),
            )
            self.locked = False

    def download_process(
        self, did_map, resources, args, kwargs, download_id, container
    ):
        ids, _names = unzip(did_map.items())
        threads = {}
        for resource, did, name, arg, kwarg in zip(
            resources, ids, _names, args, kwargs
        ):
            args = [download_id, did, container, name, resource]
            args.extend(arg)
            t = Thread(
                target=self._handle_download,
                args=args,
                kwargs=kwarg,
                name="Fido-Download-Item-" + did,
            )
            t.start()
            threads[did] = t
            if len(threads.keys()) > 4:
                while len(threads.keys()) > 4:
                    td = []
                    for k, v in threads.items():
                        if not v.is_alive():
                            td.append(k)
                    for k in td:
                        del threads[k]

    def download(
        self,
        container: str,
        resources: list[Resource] = [],
        names: list[str] = [],
        args: list[list] = None,
        kwargs: list[dict] = None,
    ):
        if args == None:
            args = [[] for i in range(len(resources))]
        if kwargs == None:
            kwargs = [{} for i in range(len(resources))]
        if not (len(names) == len(args) == len(kwargs) == len(resources)):
            raise ArgumentError(
                "resources, names, args, and kwargs must be the same length"
            )
        self.makedirs(container, exist_ok=True)
        download_id = sha256(str(time()).encode("utf-8")).hexdigest()
        did_map = {}
        for name in names:
            download_item_id = sha256(str(time()).encode("utf-8")).hexdigest()[:12]
            did_map[download_item_id] = name
            self.wait_lock()
            self.locked = True
            self.db.insert(
                {
                    "type": "queued",
                    "path": f"{container}/{name}",
                    "startedTimestamp": None,
                    "completedTimestamp": None,
                    "message": "Queued",
                    "container": container,
                    "download_id": download_id,
                    "item_id": download_item_id,
                }
            )
            self.locked = False

        proc = Thread(
            target=self.download_process,
            name=f"Fido-Downloader-{download_id}",
            args=[did_map, resources, args, kwargs, download_id, container],
        )
        proc.start()

        return self.db.search(where("download_id") == download_id)

    def clear_old_download_trackers(self):
        self.db.remove(
            ((where("type") == "complete") | (where("type") == "error"))
            & (where("completedTimestamp") < (time() - cfg()["download_entry_clear"]))
        )
