
TODO:
* show results as a list of images
* error handling
* throw out all of this custom panel stuff, and build on top of Remote Asset Libraries (when that get released)


add dependencies:
```
pip wheel 'ikea_api[httpx]' -w ./wheels
```

build:
```
blender --command extension build
```

install:
* blender -> edit -> preferences -> add-ons -> install from disk -> select the .zip file
