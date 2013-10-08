import bpy, bpy_extras, sys, datetime, mathutils
import bpy_extras.io_utils as io_utils
from collections import OrderedDict
from datetime import date
from datetime import datetime as dt
from .livi_export import radcexport, radgexport
from .livi_calc  import rad_prev, li_calc
from .vi_display import li_display, li_compliance, linumdisplay, li3D_legend
from .envi_export import enpolymatexport, pregeo
from .envi_mat import envi_materials, envi_constructions
from .envi_calc import envi_sim
from .vi_func import processf, livisimacc
from .vi_chart import chart_disp

envi_mats = envi_materials()
envi_cons = envi_constructions()

class NODE_OT_LiGExport(bpy.types.Operator):
    bl_idname = "node.ligexport"
    bl_label = "VI-Suite export"
    nodeid = bpy.props.StringProperty()

    def execute(self, context):
        context.scene.vi_display = 0
        if bpy.data.filepath and " " not in bpy.data.filepath:
            node = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
            node.reslen = 0
            bpy.data.node_groups[self.nodeid.split('@')[1]].use_fake_user = 1
            radgexport(self, node)
            node.exported = True
            if node.bl_label[0] == '*':
                node.bl_label = node.bl_label[1:]
            node.outputs[0].hide = False
            return {'FINISHED'}

        elif " "  in bpy.data.filepath:
            self.report({'ERROR'},"The directory path or Blender filename has a space in it. Please save again without any spaces and recreate this node")
            bpy.ops.node.delete()
            return {'FINISHED'}

        elif not bpy.data.filepath:
            self.report({'ERROR'},"The Blender file has not been saved. Save the Blender file and recreate this node before exporting")
            bpy.ops.node.delete()
            return {'FINISHED'}

class NODE_OT_EpwSelect(bpy.types.Operator, io_utils.ImportHelper):
    bl_idname = "node.epwselect"
    bl_label = "Select EPW file"
    bl_description = "Select the EnergyPlus weather file"
    filename = ""
    filename_ext = ".HDR;.hdr;.epw;.EPW;"
    filter_glob = bpy.props.StringProperty(default="*.HDR;*.hdr;*.epw;*.EPW;", options={'HIDDEN'})
    bl_register = True
    bl_undo = True
    nodeid = bpy.props.StringProperty()

    def draw(self,context):
        layout = self.layout
        row = layout.row()
        row.label(text="Import EPW File with FileBrowser", icon='WORLD_DATA')
        row = layout.row()

    def execute(self, context):
        if self.filepath.split(".")[-1] in ("epw", "EPW", "HDR", "hdr"):
            bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]].epwname = self.filepath
        if " " in self.filepath:
            self.report({'ERROR'}, "There is a space either in the EPW filename or its directory location. Remove this space and retry opening the file.")
        return {'FINISHED'}

    def invoke(self,context,event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class NODE_OT_HdrSelect(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    bl_idname = "node.hdrselect"
    bl_label = "Select EPW file"
    bl_description = "Select the HDR image file"
    filename = ""
    filename_ext = ".HDR;.hdr;"
    filter_glob = bpy.props.StringProperty(default="*.HDR;*.hdr;", options={'HIDDEN'})
    bl_register = True
    bl_undo = True
    nodeid = bpy.props.StringProperty()

    def draw(self,context):
        layout = self.layout
        row = layout.row()
        row.label(text="Import HDR image file with FileBrowser", icon='WORLD_DATA')
        row = layout.row()

    def execute(self, context):
        if self.filepath.split(".")[-1] in ("HDR", "hdr"):
            bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodename].hdrname = self.filepath
        if " " in self.filepath:
            self.report({'ERROR'}, "There is a space either in the HDR filename or its directory location. Remove this space and retry opening the file.")
        return {'FINISHED'}

    def invoke(self,context,event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class NODE_OT_SkySelect(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    bl_idname = "node.skyselect"
    bl_label = "Select EPW file"
    bl_description = "Select the Radiance sky file"
    filename = ""
    filename_ext = ".rad;.RAD;"
    filter_glob = bpy.props.StringProperty(default="*.RAD;*.rad;", options={'HIDDEN'})
    bl_register = True
    bl_undo = True
    nodeid = bpy.props.StringProperty()

    def draw(self,context):
        layout = self.layout
        row = layout.row()
        row.label(text="Import a Radiance sky file with the fileBrowser", icon='WORLD_DATA')
        row = layout.row()

    def execute(self, context):
        if self.filepath.split(".")[-1] in ("RAD", "rad"):
            bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodename].skyname = self.filepath
        if " " in self.filepath:
            self.report({'ERROR'}, "There is a space either in the Radiance sky filename or its directory location. Remove this space and retry opening the file.")
        return {'FINISHED'}

    def invoke(self,context,event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class NODE_OT_LiExport(bpy.types.Operator, io_utils.ExportHelper):
    bl_idname = "node.liexport"
    bl_label = "Export"
    bl_description = "Export the scene to the Radiance file format"
    bl_register = True
    bl_undo = True

    nodeid = bpy.props.StringProperty()

    def invoke(self, context, event):
        context.scene.li_disp_panel = 0
        context.scene.lic_disp_panel = 0
        context.scene.vi_display = 0
        node = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        node.bl_label = node.bl_label[1:] if node.bl_label[0] == '*' else node.bl_label
        if node.bl_label == 'LiVi Basic':
            node.resname = ("illumout", "irradout", "dfout")[int(node.analysismenu)]
            node.unit = ("Lux", "W/m"+ u'\u00b2', "DF %")[int(node.analysismenu)]
            node.skynum = int(node.skymenu) if node.analysismenu != "2" else 3
            if str(sys.platform) != 'win32':
                node.simalg = (" |  rcalc  -e '$1=47.4*$1+120*$2+11.6*$3' ", " |  rcalc  -e '$1=$1' ", " |  rcalc  -e '$1=(47.4*$1+120*$2+11.6*$3)/100' ")[int(node.analysismenu)]
            else:
                node.simalg = (' |  rcalc  -e "$1=47.4*$1+120*$2+11.6*$3" ', ' |  rcalc  -e "$1=$1" ', ' |  rcalc  -e "$1=(47.4*$1+120*$2+11.6*$3)/100" ')[int(node.analysismenu)]
            node.TZ = node.summer if node.daysav == True else node.stamer

        elif node.bl_label == 'LiVi Compliance':
            if node.analysismenu == '0':
                node.resname = 'breaamout'
                node.unit = "DF %"
                if str(sys.platform) != 'win32':
                    node.simalg = " |  rcalc  -e '$1=(47.4*$1+120*$2+11.6*$3)/100' "
                else:
                    node.simalg = ' |  rcalc  -e "$1=(47.4*$1+120*$2+11.6*$3)/100" '

            elif node.analysismenu == '1':
                node.resname = 'cfs'
                if str(sys.platform) != 'win32':
                    node.simalg = " |  rcalc  -e '$1=(47.4*$1+120*$2+11.6*$3)/100' "
                else:
                    node.simalg = ' |  rcalc  -e "$1=(47.4*$1+120*$2+11.6*$3)/100" '

        if bpy.data.filepath:
            if bpy.context.object:
                if bpy.context.object.type == 'MESH' and bpy.context.object.hide == False and bpy.context.object.layers[0] == True:
                    bpy.ops.object.mode_set(mode = 'OBJECT')

            if " " not in bpy.data.filepath:
                if node.inputs['Geometry in'].is_linked:
                    radcexport(self, node)
                    node.disp_leg = False
                    node.exported = True
                    node.outputs['Context out'].hide = False
                else:
                    self.report({'ERROR'},"No geometry node is linked")
                    node.outputs['Context out'].hide = True
            else:
                node.outputs['Context out'].hide = True
                self.report({'ERROR'},"The directory path or Blender filename has a space in it. Please save again without any spaces")
                return {'FINISHED'}
            return {'FINISHED'}
        else:
            node.outputs['Context out'].hide = True
            self.report({'ERROR'},"Save the Blender file before exporting")
            return {'FINISHED'}

class NODE_OT_RadPreview(bpy.types.Operator, io_utils.ExportHelper):
    bl_idname = "node.radpreview"
    bl_label = "Preview"
    bl_description = "Prevew the scene with Radiance"
    bl_register = True
    bl_undo = True

    nodeid = bpy.props.StringProperty()

    def invoke(self, context, event):
        simnode = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        connode = simnode.inputs['Context in'].links[0].from_node
        geonode = connode.inputs['Geometry in'].links[0].from_node
        rad_prev(self, simnode, connode, geonode, livisimacc(simnode, connode))
        return {'FINISHED'}

class NODE_OT_Calculate(bpy.types.Operator):
    bl_idname = "node.calculate"
    bl_label = "Radiance Export and Simulation"

    nodeid = bpy.props.StringProperty()

    def invoke(self, context, event):
        simnode = bpy.data.node_groups[self.nodeid.split('@')[1]].nodes[self.nodeid.split('@')[0]]
        connode = simnode.inputs['Context in'].links[0].from_node
        geonode = connode.inputs['Geometry in'].links[0].from_node

        li_calc(self, simnode, connode, geonode, livisimacc(simnode, connode))
        context.scene.vi_display = 0
        context.scene.li_disp_panel = 1
        context.scene.lic_disp_panel = 1 if connode.bl_label == 'LiVi Compliance' else 0
        context.scene.resnode = simnode.name
        context.scene.restree = self.nodeid.split('@')[1]
        return {'FINISHED'}

class VIEW3D_OT_LiDisplay(bpy.types.Operator):
    bl_idname = "view3d.lidisplay"
    bl_label = "Radiance Results Display"
    bl_description = "Display the results on the sensor surfaces"
    bl_register = True
    bl_undo = True

    def invoke(self, context, event):
        simnode = bpy.data.node_groups[context.scene.restree].nodes[context.scene.resnode]
        connode = simnode.inputs['Context in'].links[0].from_node
        geonode = connode.inputs['Geometry in'].links[0].from_node
        try:
            li_display(simnode, connode, geonode)
            bpy.ops.view3d.linumdisplay()
        except:
            self.report({'ERROR'},"No results available for display. Try re-running the calculation.")
            raise
        return {'FINISHED'}

class VIEW3D_OT_LiNumDisplay(bpy.types.Operator):
    '''Display results legend and stats in the 3D View'''
    bl_idname = "view3d.linumdisplay"
    bl_label = "Display results legend and stats in the 3D View"
    bl_options = {'REGISTER'}

    def modal(self, context, event):
        context.area.tag_redraw()
        if context.scene.vi_display == 0:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_leg, 'WINDOW')
#            bpy.types.SpaceView3D.draw_handler_remove(self._handle_stat, 'WINDOW')
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_pointres, 'WINDOW')
            if bpy.context.scene.resnode == 'LiVi Compliance':
                bpy.types.SpaceView3D.draw_handler_remove(self._handle_comp, 'WINDOW')


#        if context.scene.leg_display == 1:
#            context.scene.rp_display = False
            return {'CANCELLED'}
        return {'PASS_THROUGH'}

    def execute(self, context):
        simnode = bpy.data.node_groups[context.scene.restree].nodes[context.scene.resnode]
        connode = simnode.inputs['Context in'].links[0].from_node
        geonode = connode.inputs['Geometry in'].links[0].from_node

        if context.area.type == 'VIEW_3D':
            self._handle_leg = bpy.types.SpaceView3D.draw_handler_add(li3D_legend, (self, context, simnode, connode), 'WINDOW', 'POST_PIXEL')
            self._handle_pointres = bpy.types.SpaceView3D.draw_handler_add(linumdisplay, (self, context, simnode, geonode), 'WINDOW', 'POST_PIXEL')
            if connode.bl_label == 'LiVi Compliance':
                self._handle_comp = bpy.types.SpaceView3D.draw_handler_add(li_compliance, (self, context, connode), 'WINDOW', 'POST_PIXEL')
            context.scene.vi_display = 1
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "View3D not found, cannot run operator")
            return {'CANCELLED'}

class IES_Select(bpy.types.Operator, io_utils.ImportHelper):
    bl_idname = "livi.ies_select"
    bl_label = "Select IES file"
    bl_description = "Select the lamp IES file"
    filename = ""
    filename_ext = ".ies; .IES"
    filter_glob = bpy.props.StringProperty(default="*.ies; *.IES", options={'HIDDEN'})
    bl_register = True
    bl_undo = True

    def draw(self,context):
        layout = self.layout
        row = layout.row()
        row.label(text="Open an IES File with the file browser", icon='WORLD_DATA')

    def execute(self, context):
        lamp = bpy.context.active_object
        lamp['ies_name'] = self.filepath if " " not in self.filepath else self.report({'ERROR'}, "There is a space either in the IES filename or directory location. Rename or move the file.")
        return {'FINISHED'}

    def invoke(self,context,event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class NODE_OT_ESOSelect(bpy.types.Operator, io_utils.ImportHelper):
    bl_idname = "node.esoselect"
    bl_label = "Select EnVi results file"
    bl_description = "Select the EnVi results file to process"
    filename = ""
    filename_ext = ".eso"
    filter_glob = bpy.props.StringProperty(default="*.eso", options={'HIDDEN'})
    bl_register = True
    bl_undo = True

    nodename = bpy.props.StringProperty()

    def draw(self,context):
        layout = self.layout
        row = layout.row()
        row.label(text="Open an eso results file with the file browser", icon='WORLD_DATA')

    def execute(self, context):
        bpy.data.node_groups['VI Network'].nodes[self.nodename].resfilename = self.filepath
        return {'FINISHED'}

    def invoke(self,context,event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class NODE_OT_EnGExport(bpy.types.Operator):
    bl_idname = "node.engexport"
    bl_label = "VI-Suite export"
    bl_context = "scene"
    nodename = bpy.props.StringProperty()

    def invoke(self, context, event):
        node = bpy.data.node_groups['VI Network'].nodes[self.nodename]
        pregeo()
        node.exported = True
        node.outputs[0].hide = False
        return {'FINISHED'}

class NODE_OT_EnExport(bpy.types.Operator, io_utils.ExportHelper):
    bl_idname = "node.enexport"
    bl_label = "Export"
    bl_description = "Export the scene to the EnergyPlus file format"
    bl_register = True
    bl_undo = True
    nodename = bpy.props.StringProperty()

    def invoke(self, context, event):
        node = bpy.data.node_groups['VI Network'].nodes[self.nodename]
        if bpy.data.filepath:
            if bpy.context.object:
                if bpy.context.object.type == 'MESH':
                    bpy.ops.object.mode_set(mode = 'OBJECT')
            if " " not in str(node.filedir) and " " not in str(node.filename):
#                if not os.path.isdir(envi_settings.filedir+"/"+envi_settings.filename):
#                    os.makedirs(envi_settings.filedir+"/"+envi_settings.filename)

                enpolymatexport(self, node, envi_mats, envi_cons)
                node.exported = True
            elif " " in str(node.filedir):
                self.report({'ERROR'},"The directory path containing the Blender file has a space in it.")
                return {'FINISHED'}
            elif " " in str(node.filename):
                self.report({'ERROR'},"The Blender filename has a space in it.")
                return {'FINISHED'}
            return {'FINISHED'}
        else:
            self.report({'ERROR'},"Save the Blender file before exporting")
            return {'FINISHED'}

class NODE_OT_EnSim(bpy.types.Operator, io_utils.ExportHelper):
    bl_idname = "node.ensim"
    bl_label = "Simulate"
    bl_description = "Run EnergyPlus"
    bl_register = True
    bl_undo = True
    nodename = bpy.props.StringProperty()

    def invoke(self, context, event):
        node = bpy.data.node_groups['VI Network'].nodes[self.nodename]
        envi_sim(self, node)
        if not node.outputs:
            node.outputs.new('ViEnROut', 'Results out')
        if node.outputs[0].is_linked:
            socket1 = node.outputs[0]
            socket2 = node.outputs[0].links[0].to_socket
            bpy.data.node_groups['VI Network'].links.remove(node.outputs[0].links[0])
            bpy.data.node_groups['VI Network'].links.new(socket1, socket2)

        context.scene.li_disp_panel = 2
        return {'FINISHED'}

class NODE_OT_Chart(bpy.types.Operator, io_utils.ExportHelper):
    bl_idname = "node.chart"
    bl_label = "Chart"
    bl_description = "Create a 2D graph from the results file"
    bl_register = True
    bl_undo = True
    nodename = bpy.props.StringProperty()

    def invoke(self, context, event):
        node = bpy.data.node_groups['VI Network'].nodes[self.nodename]
        Sdate = dt.fromordinal(dt(dt.now().year, 1, 1).toordinal() + node['Start'] -1) + datetime.timedelta(hours = node.dsh - 1)
        Edate = dt.fromordinal(dt(dt.now().year, 1, 1).toordinal() + node['End'] -1 ) + datetime.timedelta(hours = node.deh - 1)

        innodes = list(OrderedDict.fromkeys([inputs.links[0].from_node for inputs in node.inputs if inputs.is_linked]))
        chart_disp(self, node, innodes, Sdate, Edate)
        return {'FINISHED'}

class NODE_OT_FileProcess(bpy.types.Operator, io_utils.ExportHelper):
    bl_idname = "node.fileprocess"
    bl_label = "Process"
    bl_description = "Process EnergyPlus results file"
    bl_register = True
    bl_undo = True
    nodename = bpy.props.StringProperty()

    def invoke(self, context, event):
        node = bpy.data.node_groups['VI Network'].nodes[self.nodename]
        processf(self, node)
        if not node.outputs:
            node.outputs.new('ViEnROut', 'Results out')
        return {'FINISHED'}