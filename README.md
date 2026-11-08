# Blender IKEA Browser
Import 3D models from ikea.com into your scene!

![Screenshot](./.github/images/screenshot.jpg?raw=true)

Note that IKEA still owns the copyright for these models, you probably don't want to be using them commercially, I guess?

If you work at IKEA and can help me to make this more legit, please get in touch <3

This is very much an early proof-of-concept, check the github issues for an approximation of a roadmap

# Dev Notes
Blender 4.2.0 uses python 3.11 specifically, so use that to install bpy and create a virtualenv for if you want to have IDE autocompletions and such:
```
python3.11 -m venv venv
venv/bin/pip install bpy blender-stubs
```

## Manual Build
```
blender --command extension build
```

## Manual Installation
* blender -> edit -> preferences -> add-ons -> install from disk -> select the .zip file

## Test without Blender
```
$ uv run ikea_lib.py --verbose search kallax
$ uv run ikea_lib.py --verbose metadata 00611642
$ uv run ikea_lib.py --verbose model 00611642
```

# Configuration
* After installation, expand the addon settings in preferences
* Set your country code (e.g., 'ie' for Ireland, 'fr' for France)
* Set your language code (e.g., 'en' for English, 'fr' for French)
* The current region and language will be displayed in the IKEA Browser panel
