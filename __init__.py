import typing as t
import pathlib
import json

import bpy
import bpy.utils.previews

from .ikea_lib import IkeaApiWrapper, IkeaException


thumbs = bpy.utils.previews.new()
ikea = IkeaApiWrapper("ie", "en")


def _get_thumbnail_icon(itemNo: str, url: t.Optional[str] = None) -> t.Optional[int]:
    if itemNo not in thumbs and bpy.app.online_access:
        if icon := ikea.get_thumbnail(itemNo, url):
            thumbs.load(itemNo, icon, "IMAGE")
    if itemNo in thumbs:
        return thumbs[itemNo].icon_id
    else:
        return None


def _update_preferences(self, context):
    global ikea
    prefs = bpy.context.preferences.addons[__package__].preferences
    ikea = IkeaApiWrapper(prefs.country, prefs.language)
    ikea.cache_dir = pathlib.Path(
        bpy.utils.extension_path_user(__package__, path="cache", create=True)
    )


class IkeaBrowserPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    country: bpy.props.StringProperty(
        name="Country", default="ie", update=_update_preferences
    )
    language: bpy.props.StringProperty(
        name="Language", default="en", update=_update_preferences
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "country")
        layout.prop(self, "language")


class IkeaImportOperator(bpy.types.Operator):
    """Import the selected product from the search results list"""

    bl_idname = "ikea.import"
    bl_label = "Import a product"

    itemNo: bpy.props.StringProperty()

    def execute(self, context) -> t.Set[str]:
        if not bpy.app.online_access:
            self.report({"ERROR"}, "IKEA Browser requires online access")
            return {"CANCELLED"}

        try:
            bpy.ops.wm.usd_import(filepath=ikea.get_model(self.itemNo), scale=0.01)
            bpy.context.object["ikeaItemNo"] = self.itemNo
        except IkeaException as e:
            self.report({"ERROR"}, str(e))
        return {"FINISHED"}


class IkeaBrowserPanel(bpy.types.Panel):
    """Browse IKEA products"""

    bl_label = "IKEA Browser"
    bl_idname = "OBJECT_PT_ikea_browser"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "IKEA"

    def draw(self, context) -> None:
        if bpy.app.online_access:
            self.layout.label(text="IKEA Browser requires online access")
            return

        layout = self.layout
        layout.prop(context.scene, "ikea_search", text="", icon="VIEWZOOM")

        grid = layout.grid_flow(even_columns=True)
        results = json.loads(context.scene.ikea_results)
        for result in results:
            box = grid.box()
            box.label(text=result["mainImageAlt"])
            if icon := _get_thumbnail_icon(result["itemNo"], result["mainImageUrl"]):
                box.template_icon(icon_value=icon, scale=10)
            btn = box.operator(IkeaImportOperator.bl_idname, text="Import")
            btn.itemNo = result["itemNo"]


class IkeaProductPanel(bpy.types.Panel):
    """Show product details"""

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

        if icon := _get_thumbnail_icon(itemNo):
            layout.template_icon(icon_value=icon, scale=10)

        pip = ikea.get_pip(itemNo)
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
    if bpy.app.online_access:
        results = ikea.search(context.scene.ikea_search)
    else:
        results = []
    context.scene.ikea_results = json.dumps(results)
    # thumbs.clear()


def register() -> None:
    bpy.types.Scene.ikea_search = bpy.props.StringProperty(
        name="Search", default="", update=_update_search
    )
    bpy.types.Scene.ikea_results = bpy.props.StringProperty(
        name="Results", default="[]"
    )
    bpy.utils.register_class(IkeaBrowserPreferences)
    bpy.utils.register_class(IkeaBrowserPanel)
    bpy.utils.register_class(IkeaProductPanel)
    bpy.utils.register_class(IkeaImportOperator)

    _update_preferences(None, None)


def unregister() -> None:
    del bpy.types.Scene.ikea_search
    del bpy.types.Scene.ikea_results
    bpy.utils.unregister_class(IkeaImportOperator)
    bpy.utils.unregister_class(IkeaProductPanel)
    bpy.utils.unregister_class(IkeaBrowserPanel)
    bpy.utils.unregister_class(IkeaBrowserPreferences)
