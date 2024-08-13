import typing as t
import ikea_api
import httpx
import pathlib
from . import httpx_sync

constants = ikea_api.Constants(country="ie", language="en")
auth_api = ikea_api.Auth(constants)
search_api = ikea_api.Search(constants)
ingka_api = ikea_api.IngkaItems(constants)
pip_api = ikea_api.PipItem(constants)
rotera_api = ikea_api.RoteraItem(constants)

cache_dir = pathlib.Path("./cache")

def log_in() -> None:
    httpx_sync.run(auth_api.get_guest_token())

def search(query: str) -> t.List[t.Dict[str, t.Any]]:
    search_results = httpx_sync.run(search_api.search(query))
    items = search_results['searchResultPage']['products']['main']['items']
    products = [i['product'] for i in items]
    results = [
        {
            "itemNo": p['itemNo'],
            #"name": p['name'],
            #"typeName": p['typeName'],
            #"itemMeasureReferenceText": p['itemMeasureReferenceText'],
            "mainImageUrl": p['mainImageUrl'],
            "mainImageAlt": p['mainImageAlt'],
            "pipUrl": p['pipUrl'],
        }
        for p
        in products
        if p['itemType'] == "ART"
    ]
    # with open("search.json", 'w') as f:
    #     json.dump(products, f, indent=4)
    # with open("results.json", 'w') as f:
    #     json.dump(results, f, indent=4)
    return results

def get_thumbnail(itemNo: str, url: str) -> str:
    cache_path = cache_dir / itemNo / "thumbnail.jpg"
    if not cache_path.exists():
        print("Downloading thumbnail for ", itemNo)
        data = httpx.get(url).content
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(data)
    return str(cache_path)

def get_model(itemNo: str) -> t.Optional[str]:
    cache_path = cache_dir / itemNo / "model.usdz"
    if not cache_path.exists():
        print("Downloading model for", itemNo)
        try:
            rotera_data = httpx_sync.run(rotera_api.get_item(itemNo))
            for model in rotera_data['models']:
                if model['format'] == "usdz":
                    data = httpx.get(model['url']).content
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_bytes(data)
                    break
            else:
                print("No USDZ model found for", itemNo)
                return None
        except Exception as e:
            print("Error downloading", itemNo, e)
            return None
    return str(cache_path)
