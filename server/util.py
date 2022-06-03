from fsspec import AbstractFileSystem
import importlib

class TargetFileSystem:
    def __init__(self, module: str = "", subclass: str = "", args: list = [], kwargs: dict = {}, root_path: str = ""):
        self.module = module
        self.subclass = subclass
        self.args = args
        self.kwargs = kwargs
        self.root_path = root_path

        self.interface: AbstractFileSystem = getattr(importlib.import_module(f"fsspec.implementations.{self.module}"), self.subclass)
    
    def _path(self, path: str):
        return self.root_path.rstrip("/") + "/" + path
    
    def open(self, path: str, **kwargs):
        return self.interface.open(self._path(path), **kwargs)
    
    def walk(self, path: str, **kwargs):
        return self.interface.walk(self._path(path), **kwargs)

    def ls(self, path: str, **kwargs):
        return self.interface.ls(self._path(path), **kwargs)