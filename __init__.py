import bpy
import pathlib
import json
from . import ikea


thumbs = bpy.utils.previews.new()


class IkeaBrowserPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    # Access with:
    #addon_prefs = bpy.context.preferences.addons[__package__]
    country: bpy.props.StringProperty(name="Country", default="ie")
    language: bpy.props.StringProperty(name="Language", default="en")

    def draw(self, context):
        layout = self.layout
        # layout.label(text="This is a preferences view for our add-on")
        layout.prop(self, "country")
        layout.prop(self, "language")


class IkeaImportOperator(bpy.types.Operator):
    """Import the selected product from the search results list"""
    bl_idname = "ikea.import"
    bl_label = "Import a product"

    itemNo: bpy.props.StringProperty()

    def execute(self, context):
        bpy.ops.wm.usd_import(filepath=ikea.get_model(self.itemNo), scale=0.01)
        return {'FINISHED'}


class IkeaBrowserPanel(bpy.types.Panel):
    """Browse IKEA products"""
    bl_label = "IKEA Browser"
    bl_idname = "OBJECT_PT_ikea_browser"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "IKEA Browser"

    #@classmethod
    #def poll(self, context):
    #    return bpy.app.online_access

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.prop(context.scene, "ikea_search", text="", icon='VIEWZOOM')

        grid = layout.grid_flow(even_columns=True)
        results = json.loads(context.scene.ikea_results)
        for result in results:
            box = grid.box()
            box.label(text=result['mainImageAlt'])
            if result['itemNo'] not in thumbs:
                thumbs.load(
                    result['itemNo'],
                    ikea.get_thumbnail(result['itemNo'], result['mainImageUrl']),
                    'IMAGE'
                )
            box.template_icon(icon_value=thumbs[result['itemNo']].icon_id, scale=10)
            btn = box.operator(IkeaImportOperator.bl_idname, text="Import")
            btn.itemNo = result['itemNo']


def update_search(self, context):
    results = ikea.search(context.scene.ikea_search)
    context.scene.ikea_results = json.dumps(results)
    thumbs.clear()


def register():
    bpy.types.Scene.ikea_search = bpy.props.StringProperty(name="Search", default="chair", update=update_search)
    bpy.types.Scene.ikea_results = bpy.props.StringProperty(name="Results", default="[]")
    bpy.utils.register_class(IkeaBrowserPreferences)
    bpy.utils.register_class(IkeaBrowserPanel)
    bpy.utils.register_class(IkeaImportOperator)

    ikea.cache_dir = pathlib.Path(bpy.utils.extension_path_user(__package__, path="cache", create=True))
    ikea.log_in()


def unregister():
    del bpy.types.Scene.ikea_search
    del bpy.types.Scene.ikea_results
    bpy.utils.unregister_class(IkeaImportOperator)
    bpy.utils.unregister_class(IkeaBrowserPanel)
    bpy.utils.unregister_class(IkeaBrowserPreferences)
