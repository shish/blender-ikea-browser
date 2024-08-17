import typing as t
import ikea_api
import httpx
import pathlib
import json
import logging

# ikea_api comes with two backends:
#   * requests (sync, native code)
#   * httpx (async, pure python)
# but we want sync in pure python...

# Also: blender wants relative imports, but running this as a script for
# testing requires absolute imports. So we try both.
try:
    from . import httpx_sync
except ImportError:
    import httpx_sync


log = logging.getLogger(__name__)


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
        log.debug("Logging in")
        httpx_sync.run(self.auth_api.get_guest_token())

    def format(self, itemNo: str) -> str:
        return ikea_api.format_item_code(itemNo)

    def search(self, query: str) -> t.List[t.Dict[str, t.Any]]:
        log.debug("Searching for %s", query)
        search_results = httpx_sync.run(self.search_api.search(query))
        # (self.cache_dir.parent / "search.json").write_text(json.dumps(search_results))

        results = []
        for i in search_results["searchResultPage"]["products"]["main"]["items"]:
            p = i["product"]
            if p["itemType"] != "ART":
                continue

            valid = True
            for field in {"itemNo", "mainImageUrl", "mainImageAlt", "pipUrl"}:
                if field not in p:
                    name = p["name"]
                    log.info(f"{name} is missing {field}")
                    valid = False

            if valid:
                results.append(
                    {
                        "itemNo": p["itemNo"],
                        # "name": p['name'],
                        # "typeName": p['typeName'],
                        # "itemMeasureReferenceText": p['itemMeasureReferenceText'],
                        "mainImageUrl": p["mainImageUrl"],
                        "mainImageAlt": p["mainImageAlt"],
                        "pipUrl": p["pipUrl"],
                    }
                )
        return results

    def get_pip(self, itemNo: str) -> t.Optional[t.Dict[str, t.Any]]:
        """ """
        log.debug("Getting PIP for %s", itemNo)
        cache_path = self.cache_dir / itemNo / "pip.json"

        if not cache_path.exists():
            try:
                log.info("Downloading pip metadata for %s", itemNo)
                data = httpx_sync.run(self.pip_api.get_item(itemNo))
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(data))
            except Exception as e:
                log.exception("Error downloading pip metadata for %s", itemNo)

        if cache_path.exists():
            return json.loads(cache_path.read_text())

        return None

    def get_thumbnail(self, itemNo: str, url: t.Optional[str]) -> t.Optional[str]:
        """
        Get a thumbnail for the given product. If it isn't in the cache already, download it.
        """
        log.debug("Getting thumbnail for %s", itemNo)
        cache_path = self.cache_dir / itemNo / "thumbnail.jpg"

        if not cache_path.exists() and url is not None:
            try:
                log.info("Downloading thumbnail for %s", itemNo)
                data = httpx.get(url).content
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(data)
            except Exception as e:
                log.exception(f"Error downloading thumbnail for Item #{itemNo}:")

        if cache_path.exists():
            return str(cache_path)

        return None

    def get_model(self, itemNo: str) -> str:
        log.debug("Getting model for %s", itemNo)
        cache_path = self.cache_dir / itemNo / "model.usdz"
        if not cache_path.exists():
            log.info("Downloading model for %s", itemNo)
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
                log.exception(f"Error downloading model for Item #{itemNo}:")
                raise IkeaException(f"Error downloading model for Item #{itemNo}: {e}")

        return str(cache_path)


if __name__ == "__main__":
    from pprint import pprint
    import sys
    import argparse

    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    ikea = IkeaApiWrapper("ie", "en")

    parser = argparse.ArgumentParser()
    parser.add_argument("query", type=str, nargs="+")
    args = parser.parse_args()

    pprint(ikea.search(" ".join(args.query)))
