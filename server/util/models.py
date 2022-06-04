from inspect import isclass
import json
from tinydb import where
from tinydb.table import Table
from tinydb.queries import QueryLike
import random, hashlib

class Resource:
    def __init__(self, uuid: str = None, **kwargs):
        self.__raw__ = kwargs
        self.__exclude__ = []
        self.__rid__ = "Resource"
        self.__uuid__ = uuid if uuid else hashlib.sha256(str(random.random()).encode("utf-8")).hexdigest()[:12]
    
    @classmethod
    def _parse_dict(cls, dct: dict):
        ret = {}
        for k, v in dct.items():
            if k == "__rid__":
                continue
            if k == "__uuid__":
                ret["uuid"] = v
                continue
            if type(v) == dict:
                if "__rid__" in v.keys():
                    if v["__rid__"] in globals().keys() and issubclass(globals()[v["__rid__"]], Resource):
                        del v["__rid__"]
                        ret[k] = globals()[v["__rid__"]].from_raw(v)
                        continue
                ret[k] = cls._parse_dict(v)
            elif type(v) == list:
                ret[k] = cls._parse_list(v)
            else:
                ret[k] = v
        return ret

    @classmethod
    def _parse_list(cls, lst: list):
        ret = []
        for i in lst:
            if type(i) == dict:
                if "__rid__" in i.keys():
                    if i["__rid__"] in globals().keys() and issubclass(globals()[i["__rid__"]], Resource):
                        del i["__rid__"]
                        ret.append(globals()[i["__rid__"]].from_raw(i))
                        continue
                ret.append(cls._parse_dict(i))
            elif type(i) == list:
                ret.append(cls._parse_list(i))
            else:
                ret.append(i)
        return ret

    @classmethod
    def from_raw(cls, data: str | dict):
        if type(data) == str:
            data = json.loads(data)
        return cls(**cls._parse_dict(data))
    
    def _drill(self, dct: dict):
        ret = {}
        for k, v in dct.items():
            if k == "__raw__" or k == "__exclude__" or k in self.__exclude__:
                continue
            if isclass(v) and issubclass(v, Resource):
                ret[k] = v.to_dict()
            elif type(v) == dict:
                ret[k] = self._drill(v)
            elif type(v) == list:
                ret[k] = self._drill_list(v)
            else:
                ret[k] = v
        return ret

    def _drill_list(self, lst: list):
        ret = []
        for i in lst:
            if i == "__raw__" or i == "__exclude__" or i in self.__exclude__:
                continue
            if isclass(i) and issubclass(i, Resource):
                ret.append(i.to_dict())
            elif type(i) == dict:
                ret.append(self._drill(i))
            elif type(i) == list:
                ret.append(self._drill_list(i))
            else:
                ret.append(i)
    
    def to_dict(self):
        return self._drill(self.__dict__)
    
    def to_dict_clean(self):
        old_ex = self.__exclude__
        self.__exclude__.extend(["__rid__", "__uuid__"])
        out = self.to_dict()
        out["uuid"] = self.__uuid__
        self.__exclude__ = old_ex
        return out
    
    @classmethod
    def from_db(cls, table: Table, query: QueryLike, one=True):
        result = table.search(query)
        if len(result) == 0:
            return None if one else []
        return cls.from_raw(result[0]) if one else [cls.from_raw(r) for r in result]
    
    def save(self, table: Table):
        table.upsert(self.to_dict(), where("__uuid__") == self.__uuid__)
        return self


class Podcast(Resource):
    def __init__(
        self,
        uuid: str = None,
        id: int = None,
        title: str = None,
        feed_url: str = None,
        feed_type: str = None,
        author: str = None,
        link: str = None,
        description: str = None,
        image: str = None,
        artwork: str = None,
        categories: dict = {}
    ):
        super().__init__(
            uuid=uuid,
            id=id,
            title=title,
            feed_url=feed_url,
            feed_type=feed_type,
            author=author,
            link=link,
            description=description,
            image=image,
            artwork=artwork,
            categories=categories
        )
        self.__rid__ = "Podcast"

        self.id = id
        self.title = title
        self.feed_url = feed_url
        self.feed_type = feed_type
        self.author = author
        self.link = link
        self.description = description
        self.image = image
        self.artwork = artwork
        self.categories = categories
    
    @classmethod
    def from_feed(cls, f: dict):
        return cls(
            id=f["id"],
            title=f["title"],
            feed_url=f["url"],
            feed_type=f["contentType"],
            author=f["author"],
            link=f["link"],
            description=f["description"],
            image=f["image"],
            artwork=f["artwork"],
            categories=f["categories"]
        )

        

