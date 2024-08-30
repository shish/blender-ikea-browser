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
        ip = thumbs.load(itemNo, filename, "IMAGE")

        # it appears that images don't always fully load when thumbs.load()
        # is called, but accessing the image_size property forces the image
        # to load fully???
        _wat = ip.image_size[0] + ip.image_size[1]

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
            bpy.ops.import_scene.gltf(filepath=ikea.get_model(self.itemNo))

            for obj in bpy.context.selected_objects:
                assert isinstance(obj, bpy.types.Object)
                obj["ikeaItemNo"] = self.itemNo
                obj.name = pip["name"]
                if not obj.parent:
                    obj.location = bpy.context.scene.cursor.location
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
        layout.prop(context.window_manager, "ikea_search", text="", icon="VIEWZOOM")

        grid = layout.grid_flow(even_columns=True)
        for result in search_results:
            box = grid.box()
            box.label(text=result["mainImageAlt"])
            icon = _get_thumbnail_icon(result["itemNo"], result["mainImageUrl"])
            box.template_icon(icon_value=icon, scale=10)
            btn = box.operator(IkeaImportOperator.bl_idname, text="Import")
            btn.itemNo = result["itemNo"]


_last_itemNo = None
_last_pip = None


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
        global _last_pip, _last_itemNo

        layout = self.layout
        itemNo = context.object.get("ikeaItemNo")

        row = layout.row()
        row.label(text="Item No")
        row.label(text=ikea.format(itemNo))

        if not bpy.app.online_access:
            layout.label(text="Enable online access to see more details")
            return

        if itemNo == _last_itemNo:
            pip = _last_pip
        else:
            pip = ikea.get_pip(itemNo)
            _last_itemNo = itemNo
            _last_pip = pip

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
        search_results = ikea.search(self.ikea_search)
    else:
        search_results = []


def register() -> None:
    bpy.types.WindowManager.ikea_search = bpy.props.StringProperty(
        name="Search", default="", update=_update_search, options={"SKIP_SAVE"}
    )
    bpy.utils.register_class(IkeaBrowserPreferences)
    bpy.utils.register_class(IkeaBrowserPanel)
    bpy.utils.register_class(IkeaProductPanel)
    bpy.utils.register_class(IkeaImportOperator)

    _init(None, None)


def unregister() -> None:
    del bpy.types.WindowManager.ikea_search
    bpy.utils.unregister_class(IkeaImportOperator)
    bpy.utils.unregister_class(IkeaProductPanel)
    bpy.utils.unregister_class(IkeaBrowserPanel)
    bpy.utils.unregister_class(IkeaBrowserPreferences)
