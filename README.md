Blender IKEA Browser
====================
Import 3D models from ikea.com into your scene!

![Screenshot](./.github/images/screenshot.jpg?raw=true)

Note that IKEA still owns the copyright for these models, you probably don't want to be using them commercially, I guess?

If you work at IKEA and can help me to make this more legit, please get in touch <3

This is very much an early proof-of-concept, check the github issues for an approximation of a roadmap

Dev notes
---------
Blender 4.2.0 uses python 3.11 specifically, so use that to install bpy and create a virtualenv for testing:
```
python3.11 -m venv venv
venv/bin/pip install 'ikea_api[httpx]' bpy blender-stubs
```

Add dependencies to be packaged:
```
pip wheel 'ikea_api[httpx]' -w ./wheels
```

Build the addon .zip file:
```
blender --command extension build
```

install:
* blender -> edit -> preferences -> add-ons -> install from disk -> select the .zip file
