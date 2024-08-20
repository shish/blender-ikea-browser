import typing as t
import pathlib
import logging

import bpy
import bpy.utils.previews  # type: ignore

from .ikea_lib import IkeaApiWrapper, IkeaException


log = logging.getLogger(__name__)
thumbs = bpy.utils.previews.new()
ikea = IkeaApiWrapper("ie", "en")
search_results = []


def _get_thumbnail_icon(itemNo: str, url: str) -> int:
    if itemNo not in thumbs:
        if not bpy.app.online_access:
            # this function _should_ never be called without online access,
            # but just in case, let's make extra sure we never make network
            # calls without it.
            raise IkeaException("Can't load thumbnail without internet access")
        filename = ikea.get_thumbnail(itemNo, url)
        thumbs.load(itemNo, filename, "IMAGE")

    return thumbs[itemNo].icon_id


def _init(self, context):
    """
    Configure global things - gets called once on startup and then again
    whenever the preferences are changed.
    """
    global ikea
    prefs = bpy.context.preferences.addons[__package__].preferences
    addon_dir = pathlib.Path(bpy.utils.extension_path_user(__package__))

    ikea = IkeaApiWrapper(prefs.country, prefs.language)
    ikea.cache_dir = addon_dir / "cache"

    logging.basicConfig(
        level=logging.DEBUG if prefs.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log.info("Initialized IKEA Browser")


class IkeaBrowserPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    country: bpy.props.StringProperty(name="Country", default="ie", update=_init)  # type: ignore
    language: bpy.props.StringProperty(name="Language", default="en", update=_init)  # type: ignore
    debug: bpy.props.BoolProperty(name="Debug", default=False, update=_init)  # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "country")
        layout.prop(self, "language")


class IkeaImportOperator(bpy.types.Operator):
    """
    Fetch a 3D model from IKEA and import it into the scene.
    """

    bl_idname = "ikea.import"
    bl_label = "Import a product"

    itemNo: bpy.props.StringProperty()  # type: ignore

    def execute(self, context) -> t.Set[str]:
        if not bpy.app.online_access:
            self.report({"ERROR"}, "IKEA Browser requires online access")
            return {"CANCELLED"}

        try:
            pip = ikea.get_pip(self.itemNo)
            bpy.ops.wm.usd_import(filepath=ikea.get_model(self.itemNo))
            # The import function creates a tree of objects
            #  - Empty (parent)
            #    - Empty (Meshes)
            #      - Mesh 1
            #      - Mesh 2
            #      - ...
            #    - Empty (Materials)
            #
            # When importing a single-mesh object, the mesh is selected,
            # but when importing a multi-mesh object, the "Meshes" Empty is
            # selected instead.
            #
            # Let's normalize by finding the top-level object and working
            # from there
            top = bpy.context.object
            while top.parent:
                top = top.parent

            # Flatten the hierarchy so that all meshes are direct children
            # of the top-level parent
            for obj in top.children_recursive:
                if obj.type == "MESH":
                    obj.parent = top
                if obj.type == "EMPTY":
                    bpy.data.objects.remove(obj)

            # Set the itemNo on all objects so that metadata is available
            # no matter which part of the object is selected
            for obj in [top] + top.children_recursive:
                obj["ikeaItemNo"] = self.itemNo

            # Let's also give things some sensible names, based on the product
            # number and incrementing a number if there are duplicates
            base_name = pip["name"]
            maybe_name = base_name
            n = 1
            while bpy.data.objects.get(maybe_name):
                maybe_name = f"{base_name} ({n+1})"
                n += 1
            top.name = maybe_name
            for n, obj in enumerate(top.children_recursive):
                obj.name = f"{top.name} Mesh {n+1}"

            # Select the top-level parent in the GUI in case the user wants
            # to move it around themselves
            bpy.context.view_layer.objects.active = top

            # Blender uses Z-up; models are imported with Y-up then rotated to face Z;
            # let's remove the rotation...
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

            # After applying transforms to normalise the object, now we move it
            # where we want it
            top.location = bpy.context.scene.cursor.location
        except IkeaException as e:
            self.report({"ERROR"}, str(e))
        return {"FINISHED"}


class IkeaBrowserPanel(bpy.types.Panel):
    """
    Browse IKEA products.

    For each product, add a button for the IkeaImportOperator.
    """

    bl_label = "IKEA Browser"
    bl_idname = "OBJECT_PT_ikea_browser"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "IKEA"

    def draw(self, context) -> None:
        if not bpy.app.online_access:
            self.layout.label(text="IKEA Browser requires online access")
            return

        layout = self.layout
        layout.prop(context.scene, "ikea_search", text="", icon="VIEWZOOM")

        grid = layout.grid_flow(even_columns=True)
        for result in search_results:
            box = grid.box()
            box.label(text=result["mainImageAlt"])
            icon = _get_thumbnail_icon(result["itemNo"], result["mainImageUrl"])
            box.template_icon(icon_value=icon, scale=10)
            btn = box.operator(IkeaImportOperator.bl_idname, text="Import")
            btn.itemNo = result["itemNo"]


class IkeaProductPanel(bpy.types.Panel):
    """
    If the currently selected object has an "ikeaItemNo" property, display
    some details about the product and a button to open the IKEA website.
    """

    bl_label = "IKEA Product"
    bl_idname = "OBJECT_PT_ikea_product"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "IKEA"

    @classmethod
    def poll(self, context):
        return context.object and context.object.get("ikeaItemNo")

    def draw(self, context) -> None:
        layout = self.layout
        itemNo = context.object.get("ikeaItemNo")

        row = layout.row()
        row.label(text="Item No")
        row.label(text=ikea.format(itemNo))

        if not bpy.app.online_access:
            layout.label(text="Enable online access to see more details")
            return

        pip = ikea.get_pip(itemNo)

        icon = _get_thumbnail_icon(itemNo, pip["mainImage"]["url"])
        layout.template_icon(icon_value=icon, scale=10)

        grid = layout.grid_flow(row_major=True, even_rows=False, columns=2)
        grid.label(text="Name")
        grid.label(text=pip["name"])
        grid.label(text="Price")
        grid.label(text=pip["price"])
        grid.label(text="Style")
        grid.label(text=pip["styleGroup"])
        grid.label(text="Type")
        grid.label(text=pip["typeName"])

        layout.operator("wm.url_open", text="Open Website").url = pip["pipUrl"]


def _update_search(self, context) -> None:
    global search_results
    if bpy.app.online_access:
        search_results = ikea.search(context.scene.ikea_search)
    else:
        search_results = []


def register() -> None:
    bpy.types.Scene.ikea_search = bpy.props.StringProperty(
        name="Search", default="", update=_update_search
    )
    bpy.utils.register_class(IkeaBrowserPreferences)
    bpy.utils.register_class(IkeaBrowserPanel)
    bpy.utils.register_class(IkeaProductPanel)
    bpy.utils.register_class(IkeaImportOperator)

    _init(None, None)


def unregister() -> None:
    del bpy.types.Scene.ikea_search
    bpy.utils.unregister_class(IkeaImportOperator)
    bpy.utils.unregister_class(IkeaProductPanel)
    bpy.utils.unregister_class(IkeaBrowserPanel)
    bpy.utils.unregister_class(IkeaBrowserPreferences)
