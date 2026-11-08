#!/usr/bin/env python3

import typing as t
import pathlib
import json
import logging
import re
import urllib.parse
import http.client
import ssl

# This ID appears to be hard-coded in the website source code?
CLIENT_ID = "4863e7d2-1428-4324-890b-ae5dede24fc6"
USER_AGENT = "Blender IKEA Browser ( https://github.com/shish/blender-ikea-browser/ )"

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
        log.debug("Request URL: %s", url + "?" + urllib.parse.urlencode(params))
        log.debug("Request headers: %s", headers)

        if "web-api.ikea.com" in url:
            headers["X-Client-Id"] = CLIENT_ID
            headers["User-Agent"] = USER_AGENT

        try:
            parsed_url = urllib.parse.urlparse(url)
            path = parsed_url.path
            if params:
                path += "?" + urllib.parse.urlencode(params)

            # Using http.client as a more robust alternative to urllib
            context = ssl.create_default_context()
            conn = http.client.HTTPSConnection(parsed_url.netloc, timeout=10, context=context)

            conn.request("GET", path, headers=headers)
            response = conn.getresponse()
            if response.status < 200 or response.status >= 300:
                raise IkeaException(f"HTTP Error {response.status}: {response.reason}")

            data = response.read()
            if response.headers.get("content-type", "").startswith("application/json"):
                log.debug(f"JSON response: {data}")
            else:
                log.debug(f"Non-JSON reponse: {len(data)} bytes of {response.headers['content-type']}")
            conn.close()
            return data
        except Exception as e:
            log.exception(f"Error fetching {url}:")
            raise IkeaException(f"Error fetching {url}: {e}")

    def is_item_no(self, itemNo: str) -> bool:
        return re.match(r"^\d{3}\.?\d{3}\.?\d{2}$", itemNo) is not None

    def compact_item_no(self, itemNo: str) -> str:
        return re.sub(r"[^0-9]", "", itemNo)

    def format_item_no(self, itemNo: str) -> str:
        itemNo = self.compact_item_no(itemNo)
        return itemNo[0:3] + "." + itemNo[3:6] + "." + itemNo[6:8]

    def search(self, query: str) -> t.List[t.Dict[str, t.Any]]:
        log.debug("Searching for %s", query)

        url = f"https://sik.search.blue.cdtapps.com/{self.country}/{self.language}/search-result-page"
        params = {
            "types": "PRODUCT",
            "q": query,
            "size": "24",
            "c": "sr",
            "v": "20210322",
        }

        if self.is_item_no(query):
            params["size"] = "1"
        else:
            params["autocorrect"] = "true"
            params["subcategories-style"] = "tree-navigation"

        try:
            search_results = json.loads(self._get(url, params=params))
            # (self.cache_dir.parent / "search.json").write_text(json.dumps(search_results))
            # search_results = json.loads((self.cache_dir.parent / "search.json").read_text())
        except Exception as e:
            log.exception(f"Error searching for {query}:")
            raise IkeaException(f"Error searching for {query}: {e}")

        results = []
        for i in search_results["searchResultPage"]["products"]["main"]["items"]:
            p = i["product"]

            valid = True
            for field in {"itemNo", "mainImageUrl", "mainImageAlt", "pipUrl"}:
                if field not in p:
                    name = p["name"]
                    log.info(f"{name} is missing {field}")
                    valid = False
            if valid and not self.get_exists(p['itemNo']):
                log.info(f"{p['name']} exists but no model is available")
                valid = False

            if valid:
                results.append(
                    {
                        "itemNo": p["itemNo"],
                        "name": p['name'],
                        # "typeName": p['typeName'],
                        # "itemMeasureReferenceText": p['itemMeasureReferenceText'],
                        "mainImageUrl": p["mainImageUrl"],
                        "mainImageAlt": p["mainImageAlt"],
                        "pipUrl": p["pipUrl"],
                    }
                )
                log.debug(f"Found product: {p['name']} ({p['itemNo']})")

        if not results:
            log.info("No products found for query: %s", query)

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
                data = json.loads(self._get(url))
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(data))
            except Exception as e:
                log.exception(f"Error downloading PIP for #{itemNo}")
                raise IkeaException(f"Error downloading PIP for #{itemNo}: {e}")

        return json.loads(cache_path.read_text())

    def get_thumbnail(self, itemNo: str, url: str) -> str:
        """
        Get a thumbnail for the given product.

        Returns the path to the downloaded thumbnail in JPEG format.
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

    def get_exists(self, itemNo: str) -> bool:
        log.debug(f"Checking if model exists for #{itemNo}")
        cache_path = self.cache_dir / itemNo / "exists.json"

        if not cache_path.exists():
            try:
                data = self._get(
                    f"https://web-api.ikea.com/{self.country}/{self.language}/rotera/data/exists/{itemNo}/"
                )
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(data)
            except Exception as e:
                log.exception(f"Error checking model existence for #{itemNo}:")
                raise IkeaException(f"Error checking model existence for #{itemNo}: {e}")

        return json.loads(cache_path.read_text())["exists"]

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
                if not self.get_exists(itemNo):
                    raise IkeaException(f"No model available for #{itemNo}")

                rotera_data = json.loads(self._get(
                    f"https://web-api.ikea.com/{self.country}/{self.language}/rotera/data/model/{itemNo}/"
                ))
                log.debug("Model metadata: %r", rotera_data)
                data = self._get(rotera_data["modelUrl"])
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(data)
            except json.decoder.JSONDecodeError:
                log.exception(f"Error downloading model for #{itemNo}:")
                raise IkeaException(f"No model available for #{itemNo}")
            except Exception as e:
                log.exception(f"Error downloading model for #{itemNo}:")
                raise IkeaException(f"Error downloading model for #{itemNo}: {e}")

        return str(cache_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--country", default="ie")
    parser.add_argument("-l", "--language", default="en")
    parser.add_argument("-v", "--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="cmd")
    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("query", type=str, nargs="+")
    metadata_parser = subparsers.add_parser("metadata")
    metadata_parser.add_argument("itemNo", type=str)
    model_parser = subparsers.add_parser("model")
    model_parser.add_argument("itemNo", type=str)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    ikea = IkeaApiWrapper(args.country, args.language)
    if args.cmd == "search":
        print(json.dumps(ikea.search(" ".join(args.query)), indent=4))
    elif args.cmd == "metadata":
        print(json.dumps(ikea.get_pip(ikea.compact_item_no(args.itemNo)), indent=4))
    elif args.cmd == "model":
        print(ikea.get_model(ikea.compact_item_no(args.itemNo)))
    else:
        print("No command specified")
