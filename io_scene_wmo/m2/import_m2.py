import bpy
import os
import time
import re
from . import m2 as m2_
from . import skin as skin_


def M2ToBlenderMesh(dir, filepath, filedata):

    print("\nImporting model: <<" + filepath + ">>")

    active_obj = bpy.context.scene.objects.active
    is_select = bpy.context.scene.objects.active.select if active_obj else False

    m2_path = os.path.splitext(filepath)[0] + ".m2"
    skin_path = os.path.splitext(filepath)[0] + "00.skin"
    
    m2_file = filedata.read_file(m2_path)
    skin_file = filedata.read_file(skin_path)

    m2 = m2_.M2File((m2_file, os.path.basename(m2_path)))
    skin = skin_.SkinFile((skin_file, os.path.basename(skin_path)))

    if not m2 or not skin:
        print("Failed to import: <<" + filepath + ">> Model import seems to have failed.")

    name = m2.name.decode("utf-8")

    vertices = []
    polygons = []
    normals = []
    tex_coords = []

    for vertex in m2.vertices:
        vertices.append((vertex.pos.x, vertex.pos.y, vertex.pos.z))
        tex_coords.append(vertex.uv)
        normals.append(vertex.normal)

    for polygon in skin.tri: 
        face = []
        for index in polygon.indices:
            face.append(skin.indices[index].Id)

        polygons.append(face)

    # create mesh
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], polygons)

    # set normals
    for index, vertex in enumerate(mesh.vertices):
        vertex.normal = normals[index]

    # set uv
    uv1 = mesh.uv_textures.new("UVMap")
    uv_layer1 = mesh.uv_layers[0]
    for i in range(len(uv_layer1.data)):
        uv = tex_coords[mesh.loops[i].vertex_index]
        uv_layer1.data[i].uv = (uv[0], 1 - uv[1])

    # unpack and convert textures
    texture_paths = []
    for texture in m2.textures:
        texture_paths.append(texture.name.decode("utf-8").rstrip('\0'))

    filedata.extract_textures_as_png(dir, texture_paths)

    # set textures
    for batch in skin.texunit:
        m2_mesh = skin.mesh[batch.submesh]

        # check if forced decompression is required here !!!
        path = os.path.splitext(
            m2.textures[m2.tex_lookup[batch.texture].Id].name.decode("utf-8").rstrip('\0')
            )[0] + ".png"

        img = None 

        try:
            img = bpy.data.images.load(os.path.join(dir, path), check_existing=True)
        except:
            print("\nFailed to load texture: " + path + " File is missing or invalid.")

        if img:
            for i in range(m2_mesh.tri_offset // 3, (m2_mesh.tri_offset + m2_mesh.num_tris) // 3):
                    uv1.data[i].image = img

    # create object
    scn = bpy.context.scene
                    
    for o in scn.objects:
        o.select = False

    nobj = bpy.data.objects.new(name, mesh)
    scn.objects.link(nobj)

    if active_obj:
        bpy.context.scene.objects.active = active_obj
        active_obj.select = is_select

    return nobj


def wmv_get_last_m2():
    preferences = bpy.context.user_preferences.addons.get("io_scene_wmo").preferences

    if preferences.wmv_path:

        lines = open(preferences.wmv_path).readlines()

        for line in reversed(lines):
            result = re.search("[^ ]*\\.*\.m2", line)
            if result:
                return result.string[result.regs[0][0]:result.regs[0][1]]

        return 


class WoW_WMO_Import_Doodad_WMV(bpy.types.Operator):
    bl_idname = 'scene.wow_wmo_import_doodad_from_wmv'
    bl_label = 'Import last M2 from WMV'
    bl_description = 'Import last M2 from WoW Model Viewer'
    bl_options = {'REGISTER'}

    def execute(self, context):

        game_data = getattr(bpy, "wow_game_data", None)

        if not game_data or not game_data.files:
            self.report({'ERROR'}, "Failed to import model. Connect to game client first.")
            return {'CANCELLED'}

        relpath = bpy.context.scene.WoWRoot.TextureRelPath
        dir = relpath if relpath else bpy.path.abspath("//") if bpy.data.is_saved else None
        m2_path = wmv_get_last_m2()

        if not m2_path:
            self.report({'ERROR'}, """WoW Model Viewer log contains no model entries. 
            \nMake sure to use compatible WMV version""")
            return {'CANCELLED'}

        obj = None

        if dir:
            try:
                obj = M2ToBlenderMesh(dir, m2_path, game_data)
            except:
                bpy.ops.mesh.primitive_cube_add()
                obj = bpy.context.scene.objects.active
                self.report({'WARNING'}, "Failed to import model. Placeholder is imported instead.")

            if bpy.context.scene.objects.active and bpy.context.scene.objects.active.select:
                obj.location = bpy.context.scene.objects.active.location
            else:
                obj.location = bpy.context.scene.cursor_location
                
            obj.WoWDoodad.Enabled = True
            obj.WoWDoodad.Path = m2_path

            bpy.ops.object.select_all(action='DESELECT')
            bpy.context.scene.objects.active = obj
            obj.select = True

        else:
            self.report({'ERROR'}, """Failed to import model. 
            \nSave your blendfile or enter texture relative path first.""")
            return {'CANCELLED'}

        self.report({'INFO'}, "Imported model: " + m2_path)

        return {'FINISHED'}


   