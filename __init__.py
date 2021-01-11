import bpy
from pathlib import Path

bl_info = {
    'name': 'Multi object shape key',
    'category': 'Mesh',
    'author': 'Taremin',
    'location': 'Propaties > Data > Multi Object Shapekey',
    'description': "",
    'version': (0, 0, 1),
    'blender': (2, 80, 0),
    'wiki_url': '',
    'tracker_url': '',
    'warning': '',
}


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


class PROPERTIES_UL_TareminMultiObjectShapekeyList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name, icon="LINKED", translate=False)
        layout.prop(item, "value", text="")


class PROPERTIES_OT_UpdateShapekeys(bpy.types.Operator):
    bl_idname = 'taremin.mos_update'
    bl_label = 'update'

    def execute(self, context):
        settings = context.scene.taremin_mos
        collection = settings.collection
        collection.clear()

        for name in self.get_shapekeys(context):
            item = collection.add()
            item.name = name
            item.value = 0.0

        return {'FINISHED'}

    def get_shapekeys(self, context):
        settings = context.scene.taremin_mos
        shapekey_map = None

        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            if obj.data.shape_keys is None:
                continue

            shapekey_names = {
                block.name for block in obj.data.shape_keys.key_blocks}

            if shapekey_map is None:
                shapekey_map = shapekey_names
            else:
                if settings.filter == 'INTERSECTION':
                    shapekey_map = shapekey_map.intersection(shapekey_names)
                elif settings.filter == 'UNION':
                    shapekey_map = shapekey_map.union(shapekey_names)
                else:
                    raise ValueError(
                        '{} is not implemented'.format(settings.filter))

        return shapekey_map if shapekey_map is not None else set()


class PROPERTIES_OT_ClearShapekeys(bpy.types.Operator):
    bl_idname = 'taremin.mos_clear'
    bl_label = 'update'

    def execute(self, context):
        settings = context.scene.taremin_mos
        settings.collection.clear()
        return {'FINISHED'}


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
        settings = context.scene.taremin_mos
        layout = self.layout

        box = layout.box()
        for obj in context.selected_objects:
            row = box.row()
            row.label(text=obj.name, translate=False)

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

        layout.template_list(
            listtype_name='PROPERTIES_UL_TareminMultiObjectShapekeyList',
            list_id="",
            dataptr=settings,
            propname="collection",
            active_dataptr=settings,
            active_propname="collection_index",
            type="DEFAULT"
        )


classesToRegister = [
    PROPERTIES_PT_TareminPanel,
    PROPERTIES_OT_UpdateShapekeys,
    PROPERTIES_OT_ClearShapekeys,
    PROPERTIES_UL_TareminMultiObjectShapekeyList,
    TareminMultiObjectShapekeyProperty,
    TareminMultiObjectShapekeyProps,
]


def register():
    for value in classesToRegister:
        bpy.utils.register_class(value)
    bpy.types.Scene.taremin_mos = bpy.props.PointerProperty(
        type=TareminMultiObjectShapekeyProps)


def unregister():
    for value in classesToRegister:
        bpy.utils.unregister_class(value)
    del bpy.types.Scene.taremin_mos
    Path(__file__).touch()


if __name__ == '__main__':
    register()
