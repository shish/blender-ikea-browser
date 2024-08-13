import typing as t
import ikea_api
import httpx
import pathlib
import json

# ikea_api comes with two backends:
#   * requests (sync, native code)
#   * httpx (async, pure python)
# but we want sync in pure python...
from . import httpx_sync


class IkeaException(Exception):
    pass


class IkeaApiWrapper:
    """
    A wrapper for the ikea_api python module, adding caching and some convenience methods.
    """

    def __init__(self, country: str, language: str):
        self.constants = ikea_api.Constants(country=country, language=language)
        self.auth_api = ikea_api.Auth(self.constants)
        self.search_api = ikea_api.Search(self.constants)
        self.pip_api = ikea_api.PipItem(self.constants)
        self.rotera_api = ikea_api.RoteraItem(self.constants)

        self.cache_dir = pathlib.Path("./cache")

    def log_in(self) -> None:
        httpx_sync.run(self.auth_api.get_guest_token())

    def format(self, itemNo: str) -> str:
        return ikea_api.format_item_code(itemNo)

    def search(self, query: str) -> t.List[t.Dict[str, t.Any]]:
        search_results = httpx_sync.run(self.search_api.search(query))
        items = search_results["searchResultPage"]["products"]["main"]["items"]
        products = [i["product"] for i in items]
        results = [
            {
                "itemNo": p["itemNo"],
                # "name": p['name'],
                # "typeName": p['typeName'],
                # "itemMeasureReferenceText": p['itemMeasureReferenceText'],
                "mainImageUrl": p["mainImageUrl"],
                "mainImageAlt": p["mainImageAlt"],
                "pipUrl": p["pipUrl"],
            }
            for p in products
            if p["itemType"] == "ART"
        ]
        # with open("search.json", 'w') as f:
        #     json.dump(products, f, indent=4)
        # with open("results.json", 'w') as f:
        #     json.dump(results, f, indent=4)
        return results


    def get_pip(self, itemNo: str) -> t.Optional[t.Dict[str, t.Any]]:
        """
        """
        cache_path = self.cache_dir / itemNo / "pip.json"

        if not cache_path.exists():
            try:
                print("Downloading pip metadata for ", itemNo)
                data = httpx_sync.run(self.pip_api.get_item(itemNo))
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(data))
            except Exception as e:
                print(f"Error downloading pip metadata for Item #{itemNo}: {e}")

        if cache_path.exists():
            return json.loads(cache_path.read_text())

        return None


    def get_thumbnail(self, itemNo: str, url: t.Optional[str]) -> t.Optional[str]:
        """
        Get a thumbnail for the given product. If it isn't in the cache already, download it.
        """
        cache_path = self.cache_dir / itemNo / "thumbnail.jpg"

        if not cache_path.exists() and url is not None:
            try:
                print("Downloading thumbnail for ", itemNo)
                data = httpx.get(url).content
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(data)
            except Exception as e:
                print(f"Error downloading thumbnail for Item #{itemNo}: {e}")

        if cache_path.exists():
            return str(cache_path)

        return None


    def get_model(self, itemNo: str) -> str:
        cache_path = self.cache_dir / itemNo / "model.usdz"
        if not cache_path.exists():
            print("Downloading model for", itemNo)
            try:
                rotera_data = httpx_sync.run(self.rotera_api.get_item(itemNo))
                for model in rotera_data["models"]:
                    if model["format"] == "usdz":
                        data = httpx.get(model["url"]).content
                        cache_path.parent.mkdir(parents=True, exist_ok=True)
                        cache_path.write_bytes(data)
                        break
                else:
                    raise IkeaException(f"No 3D model found for Item #{itemNo}")
            except Exception as e:
                raise IkeaException(f"Error downloading model for Item #{itemNo}: {e}")

        return str(cache_path)
