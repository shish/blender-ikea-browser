import typing as t
import pathlib
import json
import logging
import re
import urllib.request
import urllib.parse

log = logging.getLogger(__name__)


class IkeaException(Exception):
    pass


class IkeaApiWrapper:
    def __init__(self, country: str, language: str):
        self.country = country
        self.language = language
        self.cache_dir = pathlib.Path("./cache")

    def _get(
        self,
        url: str,
        *args,
        params: t.Dict[str, str] = {},
        headers: t.Dict[str, str] = {},
    ) -> str:
        try:
            return urllib.request.urlopen(
                urllib.request.Request(
                    url + "?" + urllib.parse.urlencode(params), headers=headers
                )
            ).read()
        except Exception as e:
            log.exception(f"Error fetching {url}:")
            raise IkeaException(f"Error fetching {url}: {e}")

    def _get_json(
        self,
        url: str,
        *args,
        params: t.Dict[str, str] = {},
        headers: t.Dict[str, str] = {},
    ) -> t.Dict[str, t.Any]:
        return json.loads(self._get(url, *args, params=params, headers=headers))

    def format(self, itemNo: str) -> str:
        itemNo = re.sub(r"[^0-9]", "", itemNo)
        return itemNo[0:3] + "." + itemNo[3:6] + "." + itemNo[6:8]

    def search(self, query: str) -> t.List[t.Dict[str, t.Any]]:
        log.debug("Searching for %s", query)
        try:
            url = f"https://sik.search.blue.cdtapps.com/{self.country}/{self.language}/search-result-page"
            params = {
                "autocorrect": "true",
                "subcategories-style": "tree-navigation",
                "types": "PRODUCT",
                "q": query,
                "size": "24",
                "c": "sr",
                "v": "20210322",
            }
            search_results = self._get_json(url, params=params)
            # (self.cache_dir.parent / "search.json").write_text(json.dumps(search_results))
            # search_results = json.loads((self.cache_dir.parent / "search.json").read_text())
        except Exception as e:
            log.exception(f"Error searching for {query}:")
            raise IkeaException(f"Error searching for {query}: {e}")

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

    def get_pip(self, itemNo: str) -> t.Dict[str, t.Any]:
        """
        Get product information for the given item number.
        """
        log.debug(f"Getting PIP for #{itemNo}")
        cache_path = self.cache_dir / itemNo / "pip.json"

        if not cache_path.exists():
            try:
                log.info(f"Downloading PIP for #{itemNo}")
                url = f"https://www.ikea.com/{self.country}/{self.language}/products/{itemNo[5:]}/{itemNo}.json"
                data = self._get_json(url)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(data))
            except Exception as e:
                log.exception(f"Error downloading PIP for #{itemNo}")
                raise IkeaException(f"Error downloading PIP for #{itemNo}: {e}")

        return json.loads(cache_path.read_text())

    def get_thumbnail(self, itemNo: str, url: str) -> str:
        """
        Get a thumbnail for the given product.
        """
        log.debug(f"Getting thumbnail for #{itemNo}")
        cache_path = self.cache_dir / itemNo / "thumbnail.jpg"

        if not cache_path.exists():
            try:
                log.info(f"Downloading thumbnail for #{itemNo}")
                data = self._get(url)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(data)
            except Exception as e:
                log.exception(f"Error downloading thumbnail for #{itemNo}:")
                raise IkeaException(f"Error downloading thumbnail for #{itemNo}: {e}")

        return str(cache_path)

    def get_model(self, itemNo: str) -> str:
        """
        Get a 3D model for the given product.

        Returns the path to the downloaded model in GLB format.
        """
        log.debug(f"Getting model for #{itemNo}")
        cache_path = self.cache_dir / itemNo / "model.glb"
        if not cache_path.exists():
            log.info(f"Downloading model for #{itemNo}")
            try:
                # This ID appears to be hard-coded in the website source code?
                headers = {"X-Client-Id": "4863e7d2-1428-4324-890b-ae5dede24fc6"}
                rotera_exists = self._get_json(
                    f"https://web-api.ikea.com/{self.country}/{self.language}/rotera/data/exists/{itemNo}",
                    headers=headers,
                )
                log.debug("Exists data: %r", rotera_exists)
                if not rotera_exists["exists"]:
                    raise IkeaException(f"No model available for #{itemNo}")

                rotera_data = self._get_json(
                    f"https://web-api.ikea.com/{self.country}/{self.language}/rotera/data/model/{itemNo}",
                    headers=headers,
                )
                log.debug("Model metadata: %r", rotera_data)
                data = urllib.request.urlopen(rotera_data["modelUrl"]).read()
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(data)
            except Exception as e:
                log.exception(f"Error downloading model for #{itemNo}:")
                raise IkeaException(f"Error downloading model for #{itemNo}: {e}")

        return str(cache_path)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--country", default="ie")
    parser.add_argument("--language", default="en")
    subparsers = parser.add_subparsers(dest="cmd")
    auth_parser = subparsers.add_parser("auth")
    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("query", type=str, nargs="+")
    metadata_parser = subparsers.add_parser("metadata")
    metadata_parser.add_argument("itemNo", type=str)
    model_parser = subparsers.add_parser("model")
    model_parser.add_argument("itemNo", type=str)
    args = parser.parse_args()

    ikea = IkeaApiWrapper(args.country, args.language)
    if args.cmd == "search":
        print(json.dumps(ikea.search(" ".join(args.query)), indent=4))
    if args.cmd == "metadata":
        print(json.dumps(ikea.get_pip(args.itemNo), indent=4))
    if args.cmd == "model":
        print(ikea.get_model(args.itemNo))
