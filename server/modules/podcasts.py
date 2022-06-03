import podcastindex

class PodcastModule:
    METHODS = ["search", "episodes"]

    def __init__(self, key: dict):
        self.key = key
        self.index = podcastindex.init(self.key)

    def search(self, term: str = ""):
        results_raw = self.index.search(term)
        return [
            {
                "id": r["id"],
                "feedUrl": r["url"],
                "channel": {
                    "name": r["title"],
                    "desc": r["description"],
                    "author": r["author"],
                    "owner": r["ownerName"],
                    "categories": r["categories"]
                },
                "images": {
                    "image": r["image"],
                    "art": r["artwork"]
                },
                "feedType": r["contentType"]
            } for r in results_raw["feeds"]
        ]
    
    def episodes(self, feed_id: str = "", limit: int = 10000, since: int | None = None):
        results_raw = self.index.episodesByFeedId(feed_id, since=since, max_results=limit)
        return [{
            "id": r["id"],
            "title": r["title"],
            "desc": r["description"],
            "publishedAt": r["datePublished"],
            "content": r["enclosureUrl"],
            "duration": r["duration"],
            "sequence": {
                "season": r["season"],
                "episode": r["episode"],
                "type": r["episodeType"]
            },
            "image": r["image"]
        } for r in results_raw["items"]]
