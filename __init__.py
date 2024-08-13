import bpy
import pathlib
import json
from . import ikea

class IkeaBrowserPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    country: bpy.props.StringProperty(name="Country", default="ie")
    language: bpy.props.StringProperty(name="Language", default="en")

    def draw(self, context):
        layout = self.layout
        # layout.label(text="This is a preferences view for our add-on")
        layout.prop(self, "country")
        layout.prop(self, "language")

class IkeaSearchOperator(bpy.types.Operator):
    """Search for IKEA products"""
    bl_idname = "ikea.search"
    bl_label = "Search for IKEA products"

    def execute(self, context):
        context.scene.ikea_results = json.dumps(ikea.search(context.scene.ikea_search))
        return {'FINISHED'}

class IkeaSelectOperator(bpy.types.Operator):
    """Select a product from the search results"""
    bl_idname = "ikea.select"
    bl_label = "Select a product"

    def execute(self, context):
        results = json.loads(context.scene.ikea_results)
        if results:
            context.scene.ikea_selected = results[0]['itemNo']
        else:
            context.scene.ikea_selected = ""
        return {'FINISHED'}

class IkeaImportOperator(bpy.types.Operator):
    """Import the selected product from the search results list"""
    bl_idname = "ikea.import"
    bl_label = "Import a product"

    def execute(self, context):
        if context.scene.ikea_selected:
            bpy.ops.wm.usd_import(filepath=ikea.get_model(context.scene.ikea_selected), scale=0.01)
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
        row.prop(context.scene, "ikea_search", text="")
        row.operator(IkeaSearchOperator.bl_idname, text="Search")

        row = layout.row()
        row.prop(context.scene, "ikea_results", text="", expand=True)
        row.operator(IkeaSelectOperator.bl_idname, text="Select")

        row = layout.row()
        row.prop(context.scene, "ikea_selected", text="")
        row.operator(IkeaImportOperator.bl_idname, text="Import")

#def update_search(self, context):
#    context.scene.ikea_results = str(ikea.search(context.scene.ikea_search))

# Registration
def register():
    #bpy.types.Scene.ikea_search = bpy.props.StringProperty(name="Search", default="chair", update=update_search)
    bpy.types.Scene.ikea_search = bpy.props.StringProperty(name="Search", default="chair")
    bpy.types.Scene.ikea_results = bpy.props.StringProperty(name="Results", default="[]")
    bpy.types.Scene.ikea_selected = bpy.props.StringProperty(name="Selected", default="")
    bpy.utils.register_class(IkeaBrowserPreferences)
    bpy.utils.register_class(IkeaBrowserPanel)
    bpy.utils.register_class(IkeaSearchOperator)
    bpy.utils.register_class(IkeaSelectOperator)
    bpy.utils.register_class(IkeaImportOperator)

    ikea.cache_dir = pathlib.Path(bpy.utils.extension_path_user(__package__, path="cache", create=True))
    # TODO: ikea.log_in()

def unregister():
    del bpy.types.Scene.ikea_search
    del bpy.types.Scene.ikea_results
    bpy.utils.unregister_class(IkeaImportOperator)
    bpy.utils.unregister_class(IkeaSelectOperator)
    bpy.utils.unregister_class(IkeaSearchOperator)
    bpy.utils.unregister_class(IkeaBrowserPanel)
    bpy.utils.unregister_class(IkeaBrowserPreferences)

# Access with:
#addon_prefs = bpy.context.preferences.addons[__package__]