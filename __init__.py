import bpy
from pathlib import Path
import json
from bpy_extras.io_utils import ExportHelper, ImportHelper

bl_info = {
    'name': 'Multi object shape key',
    'category': 'Object', # Changed category to Object as it deals with object selection
    'author': 'Taremin',
    'location': 'Propaties > Data > Multi Object Shapekey',
    'description': "",
    'version': (0, 0, 2),
    'blender': (2, 80, 0),
    'wiki_url': '',
    'tracker_url': '',
    'warning': '',
}


def get_settings(context):
    """Get the addon's settings for the current scene."""
    return context.scene.taremin_mos


class TareminMultiObjectShapekeyProperty(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="ShapeKeyName")
    value: bpy.props.FloatProperty(
        name="ShapeKeyValue", max=1.0, min=0.0, update=lambda self, context: self.update_selected_objects(context, self.name, self.value))

    def update_selected_objects(self, context, name, value):
        for obj in context.selected_objects:
            if obj.data.shape_keys is None:
                continue
            index = obj.data.shape_keys.key_blocks.find(name)
            if index == -1:
                continue
            block = obj.data.shape_keys.key_blocks[index]
            block.value = value


class MOS_SelectionPreset(bpy.types.PropertyGroup):
    """Group of properties for a single preset."""
    name: bpy.props.StringProperty(name="Preset Name", default="Preset")
    object_names: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)

    def add_object(self, name):
        item = self.object_names.add()
        item.name = name


class TareminMultiObjectShapekeyProps(bpy.types.PropertyGroup):
    collection: bpy.props.CollectionProperty(
        type=TareminMultiObjectShapekeyProperty)
    collection_index: bpy.props.IntProperty()
    filter: bpy.props.EnumProperty(
        name="ShapeKeyFilter",
        description="シェイプキーを複数のオブジェクトの和集合(合計)と積集合(共通)どちらでフィルタするか選択します",
        items=(
            ('INTERSECTION', 'Intersection', "すべての選択オブジェクトで共通するシェイプキー"),
            ('UNION', 'Union', 'すべての選択オブジェクトのすべてのシェイプキー')
        )
    )
    show_selected_objects: bpy.props.BoolProperty(
        name="Show Selected Objects",
        description="Toggle visibility of selected objects list",
        default=True
    )
    show_presets: bpy.props.BoolProperty(
        name="Show Presets",
        description="Toggle visibility of selection presets",
        default=True
    )
    show_preset_details: bpy.props.BoolProperty(
        name="Show Preset Details",
        description="Toggle visibility of selected preset's object list",
        default=True
    )
    # Preset settings are now stored per-scene
    presets: bpy.props.CollectionProperty(type=MOS_SelectionPreset)
    active_preset_index: bpy.props.IntProperty()


class PROPERTIES_UL_TareminMultiObjectShapekeyList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name, icon="LINKED", translate=False)
        layout.prop(item, "value", text="")


class PROPERTIES_OT_UpdateShapekeys(bpy.types.Operator):
    bl_idname = 'taremin.mos_update'
    bl_label = 'update'

    def execute(self, context):
        settings = get_settings(context)
        collection = settings.collection
        collection.clear()

        for name in self.get_shapekeys(context):
            item = collection.add()
            item.name = name
            item.value = 0.0

        return {'FINISHED'}

    def get_shapekeys(self, context):
        settings = get_settings(context)

        # 処理対象のメッシュオブジェクトをフィルタリング
        target_objects = [
            obj for obj in context.selected_objects
            if obj.type == 'MESH' and obj.data and obj.data.shape_keys
        ]

        if not target_objects:
            return []

        if settings.filter == 'UNION':
            # 和集合 (Union):
            # 選択されたオブジェクトを順に見ていき、各オブジェクトのシェイプキーの順序を尊重しつつ、
            # まだリストにないシェイプキーを追加していく。
            ordered_keys = []
            seen_keys = set()
            for obj in target_objects:
                for block in obj.data.shape_keys.key_blocks:
                    if block.name not in seen_keys:
                        ordered_keys.append(block.name)
                        seen_keys.add(block.name)
            return ordered_keys

        elif settings.filter == 'INTERSECTION':
            # 積集合 (Intersection):
            # 1. 全ての対象オブジェクトに共通するシェイプキー名のセットを計算する。
            key_sets = [
                {block.name for block in obj.data.shape_keys.key_blocks}
                for obj in target_objects
            ]
            common_key_names = set.intersection(*key_sets)

            if not common_key_names:
                return []

            # 2. 順序を決定するため、参照オブジェクト（アクティブオブジェクト or 最初のオブジェクト）を決定する。
            ref_obj = context.active_object if context.active_object in target_objects else target_objects[0]

            # 3. 参照オブジェクトのシェイプキーの順序に基づき、共通シェイプキーをリスト化する。
            return [
                block.name for block in ref_obj.data.shape_keys.key_blocks
                if block.name in common_key_names
            ]
        raise ValueError(f'{settings.filter} is not implemented')


class PROPERTIES_OT_ClearShapekeys(bpy.types.Operator):
    bl_idname = 'taremin.mos_clear'
    bl_label = 'update'

    def execute(self, context):
        settings = get_settings(context)
        settings.collection.clear()
        return {'FINISHED'}


class PROPERTIES_OT_SetAllShapekeyValues(bpy.types.Operator):
    bl_idname = 'taremin.mos_set_all_values'
    bl_label = 'Set All Shape Key Values'
    bl_description = "Set all shape key values in the list to a specific value"
    bl_options = {'REGISTER', 'UNDO'}

    value: bpy.props.FloatProperty(
        name="Value",
        description="Value to set for all shape keys",
        min=0.0,
        max=1.0,
        default=0.0
    )

    @classmethod
    def description(cls, context, properties):
        return f"Set all listed shape key values to {properties.value}"

    def execute(self, context):
        settings = get_settings(context)
        for item in settings.collection:
            # item.valueを更新すると、登録したupdate関数が自動で呼ばれる
            item.value = self.value
        return {'FINISHED'}


class MOS_UL_PresetList(bpy.types.UIList):
    """UIList for selection presets."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # プリセット名のみを表示
            layout.prop(item, "name", text="", emboss=False, icon='OBJECT_DATA')


class MOS_OT_AddPreset(bpy.types.Operator):
    """Save the current selection as a new preset."""
    bl_idname = "taremin.mos_preset_add"
    bl_label = "Add Selection Preset"
    bl_description = "Save the current selection of mesh objects as a new preset"
    bl_options = {'REGISTER', 'UNDO'}

    preset_name: bpy.props.StringProperty(
        name="Preset Name",
        description="Name for the new preset",
        default="New Preset"
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        settings = get_settings(context)
        selected_objs = [
            obj.name for obj in context.selected_objects if obj.type == 'MESH']

        if not selected_objs:
            self.report({'WARNING'}, "No mesh objects selected to save")
            return {'CANCELLED'}

        if not self.preset_name.strip():
            self.report({'WARNING'}, "Preset name cannot be empty")
            return {'CANCELLED'}

        new_preset = settings.presets.add()
        new_preset.name = self.preset_name
        for obj_name in selected_objs:
            new_preset.add_object(obj_name)

        settings.active_preset_index = len(settings.presets) - 1
        return {'FINISHED'}


class MOS_OT_RemovePreset(bpy.types.Operator):
    """Remove the selected preset."""
    bl_idname = "taremin.mos_preset_remove"
    bl_label = "Remove Selection Preset"
    bl_description = "Remove the selected preset"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = get_settings(context)
        return settings.presets

    def execute(self, context):
        settings = get_settings(context)
        index = settings.active_preset_index
        settings.presets.remove(index)
        settings.active_preset_index = min(
            max(0, index - 1), len(settings.presets) - 1)
        return {'FINISHED'}


class MOS_OT_LoadPreset(bpy.types.Operator):
    """Load a selection preset."""
    bl_idname = "taremin.mos_preset_load"
    bl_label = "Load Selection Preset"
    bl_description = "Selects objects based on the preset"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        items=[
            ('REPLACE', "Replace", "Replace current selection with the preset"),
            ('ADD', "Add", "Add preset objects to the current selection")
        ],
        name="Mode", default='REPLACE'
    )

    @classmethod
    def poll(cls, context):
        settings = get_settings(context)
        return settings.presets

    def execute(self, context):
        settings = get_settings(context)
        if not settings.presets or settings.active_preset_index >= len(settings.presets):
            return {'CANCELLED'}

        preset = settings.presets[settings.active_preset_index]
        object_names = [obj.name for obj in preset.object_names]

        if self.mode == 'REPLACE':
            bpy.ops.object.select_all(action='DESELECT')

        first_valid_obj = None
        for name in object_names:
            obj = bpy.data.objects.get(name)
            if obj:
                obj.select_set(True)
                if not first_valid_obj:
                    first_valid_obj = obj

        if first_valid_obj:
            context.view_layer.objects.active = first_valid_obj

        return {'FINISHED'}


class MOS_OT_MovePreset(bpy.types.Operator):
    """Move the active preset up or down in the list."""
    bl_idname = "taremin.mos_preset_move"
    bl_label = "Move Preset"
    bl_description = "Move the active preset up or down in the list"
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        items=(('UP', "Up", "Move up"),
               ('DOWN', "Down", "Move down")),
        name="Direction",
    )

    @classmethod
    def poll(cls, context):
        settings = get_settings(context)
        return settings.presets and 0 <= settings.active_preset_index < len(settings.presets)

    def execute(self, context):
        settings = get_settings(context)
        index = settings.active_preset_index

        if self.direction == 'UP' and index > 0:
            settings.presets.move(index, index - 1)
            settings.active_preset_index -= 1
        elif self.direction == 'DOWN' and index < len(settings.presets) - 1:
            settings.presets.move(index, index + 1)
            settings.active_preset_index += 1
        return {'FINISHED'}


class MOS_OT_RemoveObjectFromPreset(bpy.types.Operator):
    """Remove an object from the active preset."""
    bl_idname = "taremin.mos_preset_remove_object"
    bl_label = "Remove Object from Preset"
    bl_description = "Remove this object from the active preset"
    bl_options = {'REGISTER', 'UNDO'}

    object_name: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        settings = get_settings(context)
        return settings.presets and 0 <= settings.active_preset_index < len(settings.presets)

    def execute(self, context):
        settings = get_settings(context)
        preset = settings.presets[settings.active_preset_index]
        for i, obj in enumerate(preset.object_names):
            if obj.name == self.object_name:
                preset.object_names.remove(i)
                return {'FINISHED'}

        return {'CANCELLED'}


class MOS_OT_AddSelectedToPreset(bpy.types.Operator):
    """Add currently selected objects to the active preset."""
    bl_idname = "taremin.mos_preset_add_selected"
    bl_label = "Add Selected to Preset"
    bl_description = "Add currently selected mesh objects to the active preset (if not already present)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = get_settings(context)
        # Can run if there are selected objects and an active preset
        return context.selected_objects and settings.presets and 0 <= settings.active_preset_index < len(settings.presets)

    def execute(self, context):
        settings = get_settings(context)
        preset = settings.presets[settings.active_preset_index]

        added_count = 0
        for obj in context.selected_objects:
            if obj.type == 'MESH' and obj.name not in [o.name for o in preset.object_names]:
                preset.add_object(obj.name)
                added_count +=1

        if added_count > 0:
            self.report(
                {'INFO'}, f"Added {added_count} object(s) to preset '{preset.name}'")
            return {'FINISHED'}
        elif added_count == 0:
            self.report({'INFO'}, "No new objects to add to the preset")
            return {'FINISHED'}
        else:
            self.report({'INFO'}, "No new objects to add to the preset")
            return {'CANCELLED'}


class MOS_OT_ExportPresets(bpy.types.Operator, ExportHelper):
    """Export selection presets to a JSON file."""
    bl_idname = "taremin.mos_preset_export"
    bl_label = "Export Presets"
    bl_description = "Export all selection presets to a JSON file"
    bl_options = {'REGISTER'}

    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(
        default="*.json",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        settings = get_settings(context)

        presets_data = []
        for preset in settings.presets:
            presets_data.append({
                "name": preset.name,
                "object_names": [obj.name for obj in preset.object_names],
            })

        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(presets_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to write file: {e}")
            return {'CANCELLED'}

        self.report(
            {'INFO'}, f"Exported {len(presets_data)} presets to {self.filepath}")
        return {'FINISHED'}


class MOS_OT_ImportPresets(bpy.types.Operator, ImportHelper):
    """Import selection presets from a JSON file."""
    bl_idname = "taremin.mos_preset_import"
    bl_label = "Import Presets"
    bl_description = "Import selection presets from a JSON file"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(
        default="*.json",
        options={'HIDDEN'},
        maxlen=255,
    )

    overwrite: bpy.props.BoolProperty(
        name="Overwrite Existing Presets",
        description="If enabled, all existing presets will be removed before importing",
        default=False
    )

    def execute(self, context):
        settings = get_settings(context)

        try:
            # Use 'utf-8-sig' to correctly handle UTF-8 files with or without a BOM (Byte Order Mark),
            # which some text editors (like Windows Notepad) add automatically.
            with open(self.filepath, 'r', encoding='utf-8-sig') as f:
                presets_data = json.load(f)
        except UnicodeDecodeError:
            self.report({'ERROR'}, "File is not valid UTF-8. Please save the file with UTF-8 encoding.")
            return {'CANCELLED'}
        except json.JSONDecodeError as e:
            self.report({'ERROR'}, f"Invalid JSON format: {e}")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read or parse file: {e}")
            return {'CANCELLED'}

        if not isinstance(presets_data, list):
            self.report(
                {'ERROR'}, "JSON file is not a valid preset list (must be a JSON array).")
            return {'CANCELLED'}

        if self.overwrite:
            settings.presets.clear()

        existing_names = {p.name for p in settings.presets}
        imported_count = 0
        for preset_data in presets_data:            
            name = preset_data.get("name")
            obj_names = preset_data.get("object_names")

            if not name or not isinstance(obj_names, list):
                self.report(
                    {'WARNING'}, f"Skipping invalid preset data: {preset_data}")
                continue

            if name not in existing_names:
                new_preset = settings.presets.add()
                new_preset.name = name
                for obj_name in obj_names:
                    new_preset.add_object(obj_name)
                existing_names.add(name)
                imported_count += 1

        self.report({'INFO'}, f"Imported {imported_count} presets.")
        return {'FINISHED'}


class MultiObjectShapekeyAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    def draw(self, context):
        layout = self.layout
        layout.label(text="This addon has no user preferences.")
        layout.label(text="All settings and presets are stored within the .blend file.")


class PROPERTIES_PT_TareminPanel(bpy.types.Panel):
    bl_label = 'Multi object shape key'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        return (
            (context.object is not None) and
            (context.object.type == 'MESH')
        )

    def draw(self, context):
        settings = get_settings(context)
        layout = self.layout

        # Collapsible box for selected objects
        box = layout.box()
        row = box.row()
        row.prop(settings, "show_selected_objects", text="Selected Objects", toggle=True, icon="TRIA_DOWN" if settings.show_selected_objects else "TRIA_RIGHT")
        if settings.show_selected_objects:
            for obj in context.selected_objects:
                obj_row = box.row()
                obj_row.label(text=obj.name, translate=False)

        row = layout.row()
        col = row.column()
        col.prop(settings, 'filter', translate=False)

        row = layout.row()
        col = row.column()
        col.operator(PROPERTIES_OT_UpdateShapekeys.bl_idname,
                     text="Update")
        col = row.column()
        col.operator(PROPERTIES_OT_ClearShapekeys.bl_idname,
                     text="Clear")

        row = layout.row(align=True)
        op_reset = row.operator(
            PROPERTIES_OT_SetAllShapekeyValues.bl_idname, text="Set All to 0.0")
        op_reset.value = 0.0
        op_set = row.operator(
            PROPERTIES_OT_SetAllShapekeyValues.bl_idname, text="Set All to 1.0")
        op_set.value = 1.0

        layout.template_list(
            listtype_name='PROPERTIES_UL_TareminMultiObjectShapekeyList',
            list_id="",
            dataptr=settings,
            propname="collection",
            active_dataptr=settings,
            active_propname="collection_index",
            type="DEFAULT"
        )

        # --- Selection Presets UI ---
        box = layout.box()
        row = box.row()
        row.prop(settings, "show_presets", text="Selection Presets", toggle=True,
                 icon="TRIA_DOWN" if settings.show_presets else "TRIA_RIGHT")

        if settings.show_presets:
            row = box.row()
            row.template_list("MOS_UL_PresetList", "",
                              settings, "presets",
                              settings, "active_preset_index")

            col = row.column(align=True)
            col.operator(MOS_OT_AddPreset.bl_idname, icon='ADD', text="")
            col.operator(MOS_OT_RemovePreset.bl_idname,
                         icon='REMOVE', text="")
            col.separator()
            move_up_op = col.operator(
                MOS_OT_MovePreset.bl_idname, icon='TRIA_UP', text="")
            move_up_op.direction = 'UP'
            move_down_op = col.operator(
                MOS_OT_MovePreset.bl_idname, icon='TRIA_DOWN', text="")
            move_down_op.direction = 'DOWN'

            col.separator()
            col.operator(MOS_OT_ImportPresets.bl_idname, icon='IMPORT', text="")
            col.operator(MOS_OT_ExportPresets.bl_idname, icon='EXPORT', text="")

            row = box.row(align=True)
            op_replace = row.operator(
                MOS_OT_LoadPreset.bl_idname, text="Load (Replace)")
            op_replace.mode = 'REPLACE'
            op_add = row.operator(MOS_OT_LoadPreset.bl_idname, text="Load (Add)")
            op_add.mode = 'ADD'
            
            # --- Selected Preset Details UI ---
            if settings.presets and settings.active_preset_index < len(settings.presets):
                selected_preset = settings.presets[settings.active_preset_index]
                
                details_box = box.box() # Use a new box for the details section
                details_row = details_box.row()
                details_row.prop(settings, "show_preset_details", text=f"Contents of '{selected_preset.name}'", toggle=True,
                                 icon="TRIA_DOWN" if settings.show_preset_details else "TRIA_RIGHT")
                
                if settings.show_preset_details:
                    obj_names_list = [obj.name for obj in selected_preset.object_names]
                    if obj_names_list:
                        # Display each object with a remove button
                        for obj_name in obj_names_list:
                            row = details_box.row(align=True)
                            row.label(text=obj_name, icon='OBJECT_DATAMODE')
                            op = row.operator(MOS_OT_RemoveObjectFromPreset.bl_idname, text="", icon='X')
                            op.object_name = obj_name
                    else:
                        details_box.label(text="(No objects in this preset)", icon='INFO')
                    
                    # Add a button to add selected objects to the preset
                    details_box.separator()
                    details_box.operator(
                        MOS_OT_AddSelectedToPreset.bl_idname, 
                        text="Add Selected Objects", 
                        icon='PLUS')



classesToRegister = [
    # PropertyGroup classes that are types for other properties
    TareminMultiObjectShapekeyProperty,
    MOS_SelectionPreset,
    TareminMultiObjectShapekeyProps, # This now depends on the two above

    # UIList classes
    PROPERTIES_PT_TareminPanel,
    PROPERTIES_OT_UpdateShapekeys,
    PROPERTIES_OT_ClearShapekeys,
    PROPERTIES_OT_SetAllShapekeyValues,
    PROPERTIES_UL_TareminMultiObjectShapekeyList,
    MOS_UL_PresetList,
    MOS_OT_AddPreset,
    MOS_OT_RemovePreset,
    MOS_OT_LoadPreset,
    MOS_OT_MovePreset,
    MOS_OT_RemoveObjectFromPreset,
    MOS_OT_AddSelectedToPreset,
    MOS_OT_ExportPresets,
    MOS_OT_ImportPresets,
]


def register():
    for value in classesToRegister:
        bpy.utils.register_class(value)
    # Assign the PointerProperty. If it already exists, it will be overwritten.
    bpy.types.Scene.taremin_mos = bpy.props.PointerProperty(
        type=TareminMultiObjectShapekeyProps)


def unregister():
    for value in classesToRegister:
        bpy.utils.unregister_class(value)
    del bpy.types.Scene.taremin_mos
    Path(__file__).touch()



if __name__ == '__main__':
    register()
