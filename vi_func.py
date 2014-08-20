import bpy, os, sys, multiprocessing, mathutils, bmesh, datetime, colorsys, bgl, blf, fcntl
from math import sin, cos, asin, acos, pi
from bpy.props import IntProperty, StringProperty, EnumProperty, FloatProperty, BoolProperty, FloatVectorProperty
try:
    import matplotlib.pyplot as plt
    from .windrose import WindroseAxes
    mp = 1
except:
    mp = 0

dtdf = datetime.date.fromordinal
s = 60

def radmat(self, scene, ui):
    radname, radtype = self.name.replace(" ", "_"), ''
    if scene.render.engine == 'CYCLES' and hasattr(self.node_tree, 'nodes'):
        cycmattypes = ('Diffuse BSDF', 'Glass BSDF', 'Glossy BSDF', 'Ambient Occlusion', 'Emission', 'Transparent BSDF')
        matnode = [link.from_node for link in self.node_tree.nodes['Material Output'].inputs['Surface'].links]
        mixnodes = [link.from_node for link in matnode[0].inputs[1].links + matnode[0].inputs[2].links] if matnode[0].bl_label == 'Mix Shader' else matnode
        if mixnodes:            
            if len(mixnodes) == 2:
                trlnode = [node for node in mixnodes if node.bl_label == 'Translucent BSDF']
                glossnode = [node for node in mixnodes if node.bl_label == 'Glossy BSDF']
                transpnode = [node for node in mixnodes if node.bl_label == 'Transparent BSDF']
                diffnode = [node for node in mixnodes if node.bl_label == 'Diffuse BSDF']
                if trlnode and glossnode:
                    radtype, radnums = 'trans', '7 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f} {1:.3f} {2:.3f} {0[3]:.3f} {3:.3f}'.format(trlnode[0].inputs[0].default_value, matnode[0].inputs[0].default_value, glossnode[0].inputs[1].default_value, 1 - glossnode[0].inputs[0].default_value[3])
                if transpnode and diffnode:
                    radtype, radnums = 'antimatter', ''
                    
            elif len(mixnodes) == 1:     
                matindex = cycmattypes.index(mixnodes[0].bl_label) if mixnodes[0].bl_label in cycmattypes else 0
                matcol, matior, matrough, matemit  = mixnodes[0].inputs[0].default_value, mixnodes[0].inputs[2].default_value if matindex == 1 else 1.52, \
                    mixnodes[0].inputs[1].default_value if matindex == 0 else 0,  mixnodes[0].inputs[1].default_value if matindex == 5 else 0
                radtype = ('plastic', 'glass', 'mirror', 'antimatter', 'light', 'glass')[matindex]
                radnums = ('5 {0[0]:.2f} {0[1]:.2f} {0[2]:.2f} {1} {2:.2f}'.format(matcol, '0', matrough),\
                '4 {0[0]:.2f} {0[1]:.2f} {0[2]:.2f} {1:.3f}'.format(matcol, matior), \
                '3 {0[0]:.2f} {0[1]:.2f} {0[2]:.2f}'.format(matcol), \
                '', \
                '3 {0[0]:.2f} {0[1]:.2f} {0[2]:.2f}\n'.format([c * matemit for c in matcol]), \
                '4 {0[0]:.2f} {0[1]:.2f} {0[2]:.2f} {1:.3f}'.format(matcol, matior))[matindex]
                
    elif scene.render.engine == 'BLENDER_RENDER':
        matcol = [i * self.diffuse_intensity for i in self.diffuse_color]
        matior = self.raytrace_transparency.ior
        matrough = 1.0-self.specular_hardness/511.0
        matemit = self.emit

        if self.use_shadeless == 1 or self.livi_compliance:
            radtype, radnums = 'antimatter', ''
        elif self.emit > 0:
            radtype, radnums = 'light', '3 {0[0]:.2f} {0[1]:.2f} {0[2]:.2f}\n'.format([c * matemit for c in matcol])
        elif self.use_transparency == False and self.raytrace_mirror.use == True and self.raytrace_mirror.reflect_factor >= 0.99:
            radtype, radnums = 'mirror', '3 {0[0]:.2f} {0[1]:.2f} {0[2]:.2f}'.format(self.mirror_color)
        elif self.use_transparency == True and self.transparency_method == 'RAYTRACE' and self.alpha < 1.0 and self.translucency == 0:
            radtype = 'glass'
            if "{:.2f}".format(self.raytrace_transparency.ior) == "1.52":
                radnums = '3 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f}'.format([c * (1.0 - self.alpha) for c in matcol])
            else:
                radnums = '4 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f} {1:.3f}'.format([c * (1.0 - self.alpha) for c in matcol], matior)
        elif self.use_transparency == True and self.transparency_method == 'RAYTRACE' and self.alpha < 1.0 and self.translucency > 0.001:
            radtype, radnums  = 'trans', '7 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f} {1} {2} {3} {4}'.format(matcol, self.specular_intensity, 1.0 - self.specular_hardness/511.0, 1.0 - self.alpha, 1.0 - self.translucency)
        elif self.use_transparency == False and self.raytrace_mirror.use == True and self.raytrace_mirror.reflect_factor < 0.99:
            radtype, radnums  = 'metal', '5 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f} {1} {2}'.format(matcol, self.specular_intensity, 1.0-self.specular_hardness/511.0)
        else:
            radtype, radnums  = 'plastic', '5 {0[0]:.2f} {0[1]:.2f} {0[2]:.2f} {1:.2f} {2:.2f}'.format(matcol, self.specular_intensity, 1.0-self.specular_hardness/511.0)
        
    if not radtype:
        radtype, radnums = 'plastic', '5 {0[0]:.2f} {0[1]:.2f} {0[2]:.2f} {1} {2:.2f}'.format((0.8, 0.8, 0.8), 0, 0)
    
    radentry = '# {0} material\nvoid {0} {1}\n0\n0\n{2}\n\n'.format(radtype, radname, radnums) if radtype != 'antimatter' \
                    else '# {0} material\nvoid {0} {1}\n1 void\n0\n0\n\n'.format(radtype, radname)
    if ui == 0:
        self['radentry'] = radentry
    return(radentry)

def viparams(scene):
    fd, fn = os.path.dirname(bpy.data.filepath), os.path.splitext(os.path.basename(bpy.data.filepath))[0]

    if not os.path.isdir(os.path.join(fd, fn)):
        os.makedirs(os.path.join(fd, fn))
    if not os.path.isdir(os.path.join(fd, fn, 'obj')):
        os.makedirs(os.path.join(fd, fn, 'obj'))
    nd = os.path.join(fd, fn)
    fb, ofb, idf  = os.path.join(nd, fn), os.path.join(nd, 'obj', fn), os.path.join(nd, 'in.idf')
    scene['viparams'] = {'rm': ('rm ', 'del ')[str(sys.platform) == 'win32'], 'cat': ('cat ', 'type ')[str(sys.platform) == 'win32'],
    'cp': ('cp ', 'copy ')[str(sys.platform) == 'win32'], 'nproc': str(multiprocessing.cpu_count()), 'filepath': bpy.data.filepath,
    'filename': fn, 'filedir': fd, 'newdir': nd, 'objfilebase': ofb, 'idf_file': idf, 'filebase': fb}

def nodestate(self, opstate):
    if self['exportstate'] !=  opstate:
        self.exported = False
        if self.bl_label[0] != '*':
            self.bl_label = '*'+self.bl_label
    else:
        self.exported = True
        if self.bl_label[0] == '*':
            self.bl_label = self.bl_label[1:-1]

def face_centre(ob, obresnum, f):
    vsum = mathutils.Vector((0, 0, 0))
    for v in f.vertices:
        vsum = ob.active_shape_key.data[v].co + vsum if obresnum > 0 else ob.data.vertices[v].co + vsum
    return(vsum/len(f.vertices))

def v_pos(ob, v):
    return(ob.active_shape_key.data[v].co if ob.lires else ob.data.vertices[v].co)

def newrow(layout, s1, root, s2):
    row = layout.row()
    row.label(s1)
    row.prop(root, s2)

def retobj(name, fr, node, scene):
    if node.animmenu == "Geometry":
        return(scene['viparams']['objfilebase']+"-{}-{}.obj".format(name.replace(" ", "_"), fr))
    else:
        return(scene['viparams']['objfilebase']+"-{}-{}.obj".format(name.replace(" ", "_"), bpy.context.scene.frame_start))

def objmode():
    if bpy.context.active_object and bpy.context.active_object.type == 'MESH' and not bpy.context.active_object.hide:
        bpy.ops.object.mode_set(mode = 'OBJECT')

def retmesh(name, fr, node, scene):
    if node.animmenu in ("Geometry", "Material"):
        return(scene['viparams']['objfilebase']+"-{}-{}.mesh".format(name.replace(" ", "_"), fr))
    else:
        return(scene['viparams']['objfilebase']+"-{}-{}.mesh".format(name.replace(" ", "_"), bpy.context.scene.frame_start))

def nodeinputs(node):
    try:
        ins = [i for i in node.inputs if not i.hide]
        if ins and not all([i.is_linked for i in ins]):
            return 0
        elif ins and not all([i.links[0].from_node.exported for i in ins if i.is_linked]):
            return 0
        else:
            inodes = [i.links[0].from_node for i in ins if i.links[0].from_node.inputs]
            for inode in inodes:
                iins = [i for i in inode.inputs if not i.hide]
                if iins and not all([i.is_linked for i in iins]):
                    return 0
                elif iins and not all([i.links[0].from_node.exported for i in iins if i.is_linked]):
                    return 0
        return 1
    except:
        pass

def retmat(fr, node, scene):
    if node.animmenu == "Material":
        return("{}-{}.rad".format(scene['viparams']['filebase'], fr))
    else:
        return("{}-{}.rad".format(scene['viparams']['filebase'], scene.frame_start))

def retsky(fr, node, scene):
    if node.animmenu == "Time":
        return("{}-{}.sky".format(scene['viparams']['filebase'], fr))
    else:
        return("{}-{}.sky".format(scene['viparams']['filebase'], scene.frame_start))

def nodeexported(self):
    self.exported = 0

def negneg(x):
    if float(x) < 0:
        x = 0
    return float(x)

def clearscene(scene, op):
    if type(op) != str:
        if op.nodeid.split('@')[0] in ('LiVi Geometry', 'LiVi Simulation', 'LiVi Basic', 'LiVi Compliance', 'LiVi CBDM', 'LiVi Shadow'):
            for ob in [ob for ob in scene.objects if ob.type == 'MESH' and ob.get('licalc')]:
                scene.objects.active = ob
                while ob.data.vertex_colors:
                    bpy.ops.mesh.vertex_color_remove()

        if op.nodeid.split('@')[0] not in ('LiVi Simulation', 'LiVi Geometry'):
            for sunob in [ob for ob in scene.objects if ob.type == 'LAMP' and ob.data.type == 'SUN']:
                scene.objects.unlink(sunob)

    for ob in [ob for ob in scene.objects if ob.type == 'MESH']:
        if ob.lires == 1:
            scene.objects.unlink(ob)
        if ob.licalc == 1:
            ob.data.animation_data_clear()

    for mesh in bpy.data.meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    for lamp in bpy.data.lamps:
        if lamp.users == 0:
            bpy.data.lamps.remove(lamp)

    for oldgeo in bpy.data.objects:
        if oldgeo.users == 0:
            bpy.data.objects.remove(oldgeo)

    for sk in bpy.data.shape_keys:
        if sk.users == 0:
            for keys in sk.keys():
                keys.animation_data_clear()


def processf(pro_op, node):
    rtypes, ctypes, ztypes, zrtypes, ltypes, lrtypes = [], [], [], [], [], []
    resfile = open(node.resfilename, 'r')

    envdict = {'Site Outdoor Air Drybulb Temperature [C] !Hourly': "Temperature ("+ u'\u00b0'+"C)",
               'Site Outdoor Air Relative Humidity [%] !Hourly': 'Humidity (%)',
                'Site Wind Direction [deg] !Hourly': 'Wind Direction (deg)',
                'Site Wind Speed [m/s] !Hourly': 'Wind Speed (m/s)',
                'Site Diffuse Solar Radiation Rate per Area [W/m2] !Hourly': "Diffuse Solar (W/m"+u'\u00b2'+")",
                'Site Direct Solar Radiation Rate per Area [W/m2] !Hourly': "Direct Solar (W/m"+u'\u00b2'+")"}
    zresdict = {'Zone Air Temperature [C] !Hourly': "Temperature ({}C)".format(u'\u00b0'),
                'Zone Air System Sensible Heating Rate [W] !Hourly': 'Zone heating (W)',
                'Zone Air System Sensible Cooling Rate [W] !Hourly': 'Zone cooling (W)',
                'Zone Windows Total Transmitted Solar Radiation Rate [W] !Hourly': 'Solar gain (W)',
                'AFN Zone Infiltration Volume [m3] !Hourly': 'Infiltration (m'+u'\u00b3'+')',
                'AFN Zone Infiltration Air Change Rate [ach] !Hourly': 'Infiltration (ACH)',
                'Zone Mean Air Temperature [C] ! Hourly': 'Mean Temperature ({})'.format(u'\u00b0'),
                'Zone Mean Radiant Temperature [C] !Hourly' :'Mean Radiant ({})'.format(u'\u00b0'),
                'Zone Thermal Comfort Fanger Model PPD [%] !Hourly' :'PPD',
                'Zone Thermal Comfort Fanger Model PMV [] !Hourly' :'PMV',
                'AFN Node CO2 Concentration [ppm] !Hourly': 'CO2'}
    lresdict = {'AFN Linkage Node 1 to Node 2 Volume Flow Rate [m3/s] !Hourly': 'Linkage Flow 1 to 2',
                'AFN Linkage Node 2 to Node 1 Volume Flow Rate [m3/s] !Hourly': 'Linkage Flow 2 to 1',
                'AFN Surface Venting Window or Door Opening Factor [] !Hourly': 'Opening Factor'}
    resdict = {}

    connode = node.inputs['Context in'].links[0].from_node

    objlist = [obj.name.upper() for obj in bpy.data.objects if obj.envi_type == '1' and obj.layers[1] == True] if connode.bl_idname != 'ViEnInNode' else connode['oblist']

    for line in resfile.readlines():
        linesplit = line.strip('\n').split(',')

        if linesplit[0] in resdict:
            resdict[linesplit[0]].append(linesplit[1])
            if linesplit[0] == dos:
                resdict['Month'].append(linesplit[2])
                resdict['Day'].append(linesplit[3])
                resdict['Hour'].append(linesplit[5])

        elif len(linesplit) > 3 and linesplit[2] == 'Day of Simulation[]':
            resdict[linesplit[0]], resdict['Month'],  resdict['Day'], resdict['Hour'], dos, node['rtypes'] = ['Day of Simulation'], [], [], [], linesplit[0], ['Time']

        elif len(linesplit) > 3 and linesplit[2] == 'Environment':
            if 'Climate' not in node['rtypes']:
                node['rtypes']+= ['Climate']
            try:
                resdict[linesplit[0]] = ['Climate', envdict[linesplit[3]]]
                ctypes.append(envdict[linesplit[3]])
            except:
                pass

        elif len(linesplit) > 3 and linesplit[2] in objlist:
            if 'Zone' not in node['rtypes']:
               node['rtypes'] += ['Zone']
            try:
                resdict[linesplit[0]] = [linesplit[2], zresdict[linesplit[3]]]
                if linesplit[2] not in ztypes:
                    ztypes.append(linesplit[2])
                if zresdict[linesplit[3]] not in zrtypes:
                    zrtypes.append(zresdict[linesplit[3]])
            except:
                pass

        elif len(linesplit) > 3 and linesplit[3] in lresdict:
            if 'Linkage' not in node['rtypes']:
               node['rtypes'] += ['Linkage']
            try:
                resdict[linesplit[0]] = [linesplit[2], lresdict[linesplit[3]]]
                if linesplit[2] not in ltypes:
                    ltypes.append(linesplit[2])
                if lresdict[linesplit[3]] not in lrtypes:
                    lrtypes.append(lresdict[linesplit[3]])
            except:
                pass

    resfile.close()
    node['dos'], node['resdict'], node['ctypes'], node['ztypes'], node['zrtypes'], node['ltypes'], node['lrtypes'], node.dsdoy, node.dedoy = dos, resdict, ctypes, ztypes, zrtypes, ltypes, lrtypes, int(resdict[dos][1]), int(resdict[dos][-1])

def iprop(iname, idesc, imin, imax, idef):
    return(IntProperty(name = iname, description = idesc, min = imin, max = imax, default = idef))
def eprop(eitems, ename, edesc, edef):
    return(EnumProperty(items=eitems, name = ename, description = edesc, default = edef))
def bprop(bname, bdesc, bdef):
    return(BoolProperty(name = bname, description = bdesc, default = bdef))
def sprop(sname, sdesc, smaxlen, sdef):
    return(StringProperty(name = sname, description = sdesc, maxlen = smaxlen, default = sdef))
def fprop(fname, fdesc, fmin, fmax, fdef):
    return(FloatProperty(name = fname, description = fdesc, min = fmin, max = fmax, default = fdef))
def fvprop(fvsize, fvname, fvattr, fvdef, fvsub, fvmin, fvmax):
    return(FloatVectorProperty(size = fvsize, name = fvname, attr = fvattr, default = fvdef, subtype =fvsub, min = fvmin, max = fvmax))
def niprop(iname, idesc, imin, imax, idef):
        return(IntProperty(name = iname, description = idesc, min = imin, max = imax, default = idef, update = nodeexported))
def neprop(eitems, ename, edesc, edef):
    return(EnumProperty(items=eitems, name = ename, description = edesc, default = edef, update = nodeexported))
def nbprop(bname, bdesc, bdef):
    return(BoolProperty(name = bname, description = bdesc, default = bdef, update = nodeexported))
def nsprop(sname, sdesc, smaxlen, sdef):
    return(StringProperty(name = sname, description = sdesc, maxlen = smaxlen, default = sdef, update = nodeexported))
def nfprop(fname, fdesc, fmin, fmax, fdef):
    return(FloatProperty(name = fname, description = fdesc, min = fmin, max = fmax, default = fdef, update = nodeexported))
def nfvprop(fvname, fvattr, fvdef, fvsub):
    return(FloatVectorProperty(name=fvname, attr = fvattr, default = fvdef, subtype = fvsub, update = nodeexported))

def boundpoly(obj, mat, poly, enng):
    if mat.envi_boundary:
        polyloc = obj.matrix_world*mathutils.Vector(poly.center)
        for node in enng.nodes:
            if hasattr(node, 'zone'):
                if node.inputs[mat.name+'_b'].is_linked == True:
                    bobj = bpy.data.objects[node.inputs[mat.name+'_b'].links[0].from_node.zone]
                    for bpoly in bobj.data.polygons:
                        bpolyloc = bobj.matrix_world*mathutils.Vector(bpoly.center)
                        if bobj.data.materials[bpoly.material_index] == mat and max(bpolyloc - polyloc) < 0.001 and abs(bpoly.area - poly.area) < 0.01:
                            return(("Surface", node.inputs[mat.name+'_b'].links[0].from_node.zone+'_'+str(bpoly.index), "NoSun", "NoWind"))

                elif node.outputs[mat.name+'_b'].is_linked == True:
                    bobj = bpy.data.objects[node.outputs[mat.name+'_b'].links[0].to_node.zone]
                    for bpoly in bobj.data.polygons:
                        bpolyloc = bobj.matrix_world*mathutils.Vector(bpoly.center)
                        if bobj.data.materials[bpoly.material_index] == mat and max(bpolyloc - polyloc) < 0.001 and abs(bpoly.area - poly.area) < 0.01:
                            return(("Surface", node.outputs[mat.name+'_b'].links[0].to_node.zone+'_'+str(bpoly.index), "NoSun", "NoWind"))
            else:
                return(("Outdoors", "", "SunExposed", "WindExposed"))
        else:
            return(("Outdoors", "", "SunExposed", "WindExposed"))
    elif mat.envi_thermalmass:
        return(("Adiabatic", "", "NoSun", "NoWind"))
    else:
        return(("Outdoors", "", "SunExposed", "WindExposed"))


def objvol(op, obj):
    bm , floor, roof, mesh = bmesh.new(), [], [], obj.data
    bm.from_object(obj, bpy.context.scene)
    for f in mesh.polygons:
        if obj.data.materials[f.material_index].envi_con_type == 'Floor':
            floor.append((triarea(obj, f), (obj.matrix_world*mathutils.Vector(f.center))[2]))
        elif obj.data.materials[f.material_index].envi_con_type == 'Roof':
            roof.append((triarea(obj, f), (obj.matrix_world*mathutils.Vector(f.center))[2]))
    zfloor = list(zip(*floor))
    if not zfloor and op:
        op.report({'INFO'},"Zone has no floor area")
#    else:
#        taf = sum(zfloor[0])
#    avhf = sum([(zfloor[0][i]*zfloor[1][i])/taf for i in range(len(zfloor[0]))])
#    zroof = list(zip(*roof))
#    tar = sum(zroof[0])
#    avhr = sum([(zroof[0][i]*zroof[1][i])/tar for i in range(len(zroof[0]))])

    return(bm.calc_volume()*obj.scale[0]*obj.scale[1]*obj.scale[2])
#    return((avhr - avhf)*(taf+tar)*obj.scale[0]*obj.scale[1]*obj.scale[2]/2)


def ceilheight(obj, vertz):
    mesh = obj.data
    for vert in mesh.vertices:
        vertz.append((obj.matrix_world * vert.co)[2])
    zmax, zmin = max(vertz), min(vertz)
    ceiling = [max((obj.matrix_world * mesh.vertices[poly.vertices[0]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[1]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[2]].co)[2]) for poly in mesh.polygons if max((obj.matrix_world * mesh.vertices[poly.vertices[0]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[1]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[2]].co)[2]) > 0.9 * zmax]
    floor = [min((obj.matrix_world * mesh.vertices[poly.vertices[0]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[1]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[2]].co)[2]) for poly in mesh.polygons if min((obj.matrix_world * mesh.vertices[poly.vertices[0]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[1]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[2]].co)[2]) < zmin + 0.1 * (zmax - zmin)]
    return(sum(ceiling)/len(ceiling)-sum(floor)/len(floor))

def triarea(obj, face):
    omw = obj.matrix_world
    vs = [omw*mathutils.Vector(face.center)] + [omw*obj.data.vertices[v].co for v in face.vertices] + [omw*obj.data.vertices[face.vertices[0]].co]
    return(vsarea(obj, vs))

def vsarea(obj, vs):
    if len(vs) == 5:
        cross = mathutils.Vector.cross(vs[3]-vs[1], vs[3]-vs[2])
        return(0.5*(cross[0]**2 + cross[1]**2 +cross[2]**2)**0.5)
    else:
        i, area = 0, 0
        while i < len(vs) - 2:
            cross = mathutils.Vector.cross(vs[0]-vs[1+i], vs[0]-vs[2+i])
            area += 0.5*(cross[0]**2 + cross[1]**2 +cross[2]**2)**0.5
            i += 1
        return(area)

def rettimes(ts, fs, us):
    tot = range(min(len(ts), len(fs), len(us)))
    fstrings, ustrings, tstrings = [[] for t in tot],  [[] for t in tot], ['Through: {}/{}'.format(dtdf(ts[t]).month, dtdf(ts[t]).day) for t in tot]
    for t in tot:
        fstrings[t]= ['For: '+''.join(f) for f in fs[t].split(' ') if f.strip(' ') != '']
        for uf, ufor in enumerate(us[t].split(';')):
            ustrings[t].append([])
            for ut, utime in enumerate(ufor.split(',')):
                ustrings[t][uf].append(['Until: '+','.join([u for u in utime.split(' ') if u.strip(' ')])])
    return(tstrings, fstrings, ustrings)

def windcompass():
    rad1 = 1.4
    dep = 2.8
    lettwidth = 0.3
    lettheight = 0.15
    bpy.ops.mesh.primitive_torus_add(location=(0.0, 0.0, 0.0), view_align=False, rotation=(0.0, 0.0, 0.0), major_segments=48, minor_segments=12, major_radius=2.5, minor_radius=0.01)
    bpy.ops.mesh.primitive_cone_add(location=(0.0, rad1, 0.0), view_align=False, rotation=(pi*-0.5, 0.0, 0.0), radius1 = 0.01, depth = dep)
    bpy.ops.mesh.primitive_cone_add(location=((rad1**2/2)**0.5, (rad1**2/2)**0.5, 0.0), view_align=False, rotation=(pi*-0.5, 0.0, pi*-0.25), radius1 = 0.01, depth = dep)
    bpy.ops.mesh.primitive_cone_add(location=(rad1, 0.0, 0.0), view_align=False, rotation=(pi*-0.5, 0.0, pi*-0.5), radius1 = 0.01, depth = dep)
    bpy.ops.mesh.primitive_cone_add(location=((rad1**2/2)**0.5, -(rad1**2/2)**0.5, 0.0), view_align=False, rotation=(pi*-0.5, 0.0, pi*-0.75), radius1 = 0.01, depth = dep)
    bpy.ops.mesh.primitive_cone_add(location=(0.0, -rad1, 0.0), view_align=False, rotation=(pi*-0.5, 0.0, pi*-1), radius1 = 0.01, depth = dep)
    bpy.ops.mesh.primitive_cone_add(location=(-(rad1**2/2)**0.5, -(rad1**2/2)**0.5, 0.0), view_align=False, rotation=(pi*-0.5, 0.0, pi*-1.25), radius1 = 0.01, depth = dep)
    bpy.ops.mesh.primitive_cone_add(location=(-rad1, 0.0, 0.0), view_align=False, rotation=(pi*-0.5, 0.0, pi*-1.5), radius1 = 0.01, depth = dep)
    bpy.ops.mesh.primitive_cone_add(location=(-(rad1**2/2)**0.5, (rad1**2/2)**0.5, 0.0), view_align=False, rotation=(pi*-0.5, 0.0, pi*-1.75), radius1 = 0.01, depth = dep)
    bpy.ops.object.text_add(view_align=False, enter_editmode=False, location=(-lettheight*1.3, dep, 0.0), rotation=(0.0, 0.0, 0.0))
    txt = bpy.context.active_object
    txt.data.body = 'N'
    txt.scale = (0.5, 0.5, 0.5)
    bpy.ops.object.text_add(view_align=False, enter_editmode=False, location=((dep**2/2)**0.5-lettheight, (1+dep**2/2)**0.5, 0.0), rotation=(0.0, 0.0, pi*-0.25))
    txt = bpy.context.active_object
    txt.data.body = 'NE'
    txt.scale = (0.4, 0.4, 0.4)
    bpy.ops.object.text_add(view_align=False, enter_editmode=False, location=(dep, -lettheight, 0.0), rotation=(0.0, 0.0, 0.0))
    txt = bpy.context.active_object
    txt.data.body = 'W'
    txt.scale = (0.5, 0.5, 0.5)
    bpy.ops.object.text_add(view_align=False, enter_editmode=False, location=((dep**2/2)**0.5, -lettwidth-lettheight-(dep**2/2)**0.5, 0.0), rotation=(0.0, 0.0, pi*0.25))
    txt = bpy.context.active_object
    txt.data.body = 'SW'
    txt.scale = (0.4, 0.4, 0.4)
    bpy.ops.object.text_add(view_align=False, enter_editmode=False, location=(-lettwidth/3, -dep-lettwidth*1.3, 0.0), rotation=(0.0, 0.0, 0.0))
    txt = bpy.context.active_object
    txt.data.body = 'S'
    txt.scale = (0.5, 0.5, 0.5)
    bpy.ops.object.text_add(view_align=False, enter_editmode=False, location=(-(dep**2/2)**0.5-lettwidth-0.1, -lettwidth/2-(dep**2/2)**0.5, 0.0), rotation=(0.0, 0.0, pi*-0.25))
    txt = bpy.context.active_object
    txt.data.body = 'SE'
    txt.scale = (0.4, 0.4, 0.4)
    bpy.ops.object.text_add(view_align=False, enter_editmode=False, location=(-lettwidth-dep, -lettheight, 0.0), rotation=(0.0, 0.0, 0.0))
    txt = bpy.context.active_object
    txt.data.body = 'E'
    txt.scale = (0.5, 0.5, 0.5)
    bpy.ops.object.text_add(view_align=False, enter_editmode=False, location=(-(dep**2/2)**0.5-lettwidth, -(lettheight+lettwidth)*0.5+(dep**2/2)**0.5, 0.0), rotation=(0.0, 0.0, pi*0.25))
    txt = bpy.context.active_object
    txt.data.body = 'NW'
    txt.scale = (0.4, 0.4, 0.4)
    arrverts = ((0.05, -0.25, 0.0), (-0.05, -0.25, 0.0), (0.05, 0.25, 0.0), (-0.05, 0.25, 0.0), (0.15, 0.1875, 0.0), (-0.15, 0.1875, 0.0), (0.0, 0.5, 0.0))
    arrfaces = ((1, 0, 2, 3), (2, 4, 6, 5, 3))
    arrme = bpy.data.meshes.new('windarrow')
    arrob = bpy.data.objects.new('windarrow', arrme)
    arrme.from_pydata(arrverts, [], arrfaces)
    arrme.update()
    bpy.context.scene.objects.link(arrob)

def rgb2h(rgb):
    return colorsys.rgb_to_hsv(rgb[0]/255.0,rgb[1]/255.0,rgb[2]/255.0)[0]

def livisimacc(simnode, connode):
    return(simnode.csimacc if connode.bl_label in ('LiVi Compliance', 'LiVi CBDM') else simnode.simacc)

def drawpoly(x1, y1, x2, y2):
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glColor4f(1.0, 1.0, 1.0, 0.8)
    bgl.glBegin(bgl.GL_POLYGON)
    bgl.glVertex2i(x1, y2)
    bgl.glVertex2i(x2, y2)
    bgl.glVertex2i(x2, y1)
    bgl.glVertex2i(x1, y1)
    bgl.glEnd()
    bgl.glDisable(bgl.GL_BLEND)

def drawloop(x1, y1, x2, y2):
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)
    bgl.glBegin(bgl.GL_LINE_LOOP)
    bgl.glVertex2i(x1, y2)
    bgl.glVertex2i(x2, y2)
    bgl.glVertex2i(x2, y1)
    bgl.glVertex2i(x1, y1)
    bgl.glEnd()

def drawfont(text, fi, lencrit, height, x1, y1):
    blf.position(fi, x1, height - y1 - lencrit*26, 0)
    blf.draw(fi, text)

def mtx2vals(mtxlines, fwd, locnode):
    if locnode:
        records = (datetime.datetime(datetime.datetime.now().year, locnode.endmonth, 1) - datetime.datetime(datetime.datetime.now().year, locnode.startmonth, 1)).days*24
    else:
        for records, line in enumerate(mtxlines):
            if line == '\n':
                break
    try:
        import numpy
        np = 1
    except:
        np = 0

    vecvals = numpy.array([[x%24, (fwd+int(x/24))%7] + [0 for p in range(146)] for x in range(0,records)]) if np ==1 else [[x%24, (fwd+int(x/24))%7] + [0 for p in range(146)] for x in range(0,records)]
    vals = numpy.zeros((146)) if np ==1 else [0 for x in range(146)]
#    vals =  numpy.array([[0,1,2] for x in range(146)]) if np ==1 else [[0,1,2] for x in range(146)]

    hour = 0
    patch = 2
    for fvals in mtxlines:
        try:
            sumvals = sum([float(lv) for lv in fvals.split(" ")])/3
#            indvals = [float(lv) for lv in fvals.split(" ")]
            if sumvals > 0:
                vals[patch - 2] += sumvals
#                for i, v in enumerate(vals[patch - 2]):
#                    vals[patch - 2][i] += indvals[i]

                vecvals[hour][patch] = sumvals
            hour += 1
        except:
            if fvals != "\n":
                hour += 1
            else:
                patch += 1
                hour = 0
    if np == 1:
        return(vecvals.tolist(), vals)
    else:
        return(vecvals, vals)

def framerange(scene, anim):
    if anim == 'Static':
        return(range(scene.frame_current, scene.frame_current +1))
    else:
        return(range(scene.frame_start, scene.frame_end +1))

def frameindex(scene, anim):
    if anim == 'Static':
        return(range(0, 1))
    else:
        return(range(0, scene.frame_end - scene.frame_start +1))

def retobjs(otypes):
    scene = bpy.context.scene
    if otypes == 'livig':
        return([geo for geo in scene.objects if geo.type == 'MESH' and len(geo.data.materials) > 0 and not geo.children  and 'lightarray' not in geo.name \
        and geo.hide == False and geo.layers[scene.active_layer] == True and geo.get('VIType') not in ('SPathMesh', 'SunMesh', 'Wind_Plane')])
    elif otypes == 'livigengeo':
        return([geo for geo in scene.objects if geo.type == 'MESH' and not any([m.livi_sense for m in geo.data.materials])])
    elif otypes == 'livigengeosel':
        return([geo for geo in scene.objects if geo.type == 'MESH' and geo.select == True and not any([m.livi_sense for m in geo.data.materials])])
    elif otypes == 'livil':
        return([geo for geo in scene.objects if (geo.ies_name != "" or 'lightarray' in geo.name) and geo.hide == False and geo.layers[scene.active_layer] == True])
    elif otypes == 'livic':
        return([geo for geo in scene.objects if geo.type == 'MESH' and geo.get('licalc') and geo.lires == 0 and geo.hide == False and geo.layers[scene.active_layer] == True])
    elif otypes == 'livir':
        return([geo for geo in bpy.data.objects if geo.type == 'MESH' and True in [m.livi_sense for m in geo.data.materials] and geo.get('licalc') and geo.layers[scene.active_layer] == True])
    elif otypes == 'envig':
        return([geo for geo in scene.objects if geo.type == 'MESH' and geo.hide == False and geo.layers[0] == True])
    elif otypes == 'ssc':
        return([geo for geo in scene.objects if geo.type == 'MESH' and geo.get('licalc') and geo.lires == 0 and geo.hide == False and geo.layers[scene.active_layer] == True])

def viewdesc(context):
    region = context.region
    (width, height) = [getattr(region, s) for s in ('width', 'height')]
    mid_x, mid_y = width/2, height/2
    return(mid_x, mid_y, width, height)


def draw_index(context, leg, mid_x, mid_y, width, height, index, vec):
    vec = mathutils.Vector((vec[0] / vec[3], vec[1] / vec[3], vec[2] / vec[3]))
    x, y = int(mid_x + vec[0] * mid_x), int(mid_y + vec[1] * mid_y)
    blf.position(0, x, y, 0)
    if (leg == 1 and (x > 120 or y < height - 530)) or leg == 0:
        blf.draw(0, str(index))

def sunpath1(self, context):
    sunpath()

def sunpath2(scene):
    sunpath()

def sunpath():
    # For future reference I can also project an emmisve sky texture on a sphere using the normal texture coordinate.
    scene = bpy.context.scene
    sun = [ob for ob in scene.objects if ob.get('VIType') == 'Sun'][0]
    skysphere = [ob for ob in scene.objects if ob.get('VIType') == 'SkyMesh'][0]

    if 0 in (sun['solhour'] == scene.solhour, sun['solday'] == scene.solday, sun['soldistance'] == scene.soldistance):
        sunob = [ob for ob in scene.objects if ob.get('VIType') == 'SunMesh'][0]
        spathob = [ob for ob in scene.objects if ob.get('VIType') == 'SPathMesh'][0]
        beta, phi = solarPosition(scene.solday, scene.solhour, scene['latitude'], scene['longitude'])[2:]
        sunob.location.z = sun.location.z = spathob.location.z + scene.soldistance * sin(beta)
        sunob.location.x = sun.location.x = spathob.location.x -(scene.soldistance**2 - (sun.location.z-spathob.location.z)**2)**0.5  * sin(phi)
        sunob.location.y = sun.location.y = spathob.location.y -(scene.soldistance**2 - (sun.location.z-spathob.location.z)**2)**0.5 * cos(phi)
        sun.rotation_euler = pi * 0.5 - beta, 0, -phi
        spathob.scale = 3 * [scene.soldistance/100]
        skysphere.scale = 3 * [1.05 * scene.soldistance/100]
        sunob.scale = 3*[scene.soldistance/100]

        if scene.render.engine == 'CYCLES':
            if bpy.data.worlds['World'].node_tree:
                if 'Sky Texture' in [no.bl_label for no in bpy.data.worlds['World'].node_tree.nodes]:
                    bpy.data.worlds['World'].node_tree.nodes['Sky Texture'].sun_direction = -sin(phi), -cos(phi), sin(beta)
            if sun.data.node_tree:
                for blnode in [node for node in sun.data.node_tree.nodes if node.bl_label == 'Blackbody']:
                    blnode.inputs[0].default_value = 2000 + 3500*sin(beta)**0.5 if beta > 0 else 2000
                for emnode in [node for node in sun.data.node_tree.nodes if node.bl_label == 'Emission']:
                    emnode.inputs[1].default_value = 5 * sin(beta) if beta > 0 else 0
            if sunob.data.materials[0].node_tree:
                for smblnode in [node for node in sunob.data.materials[0].node_tree.nodes if sunob.data.materials and node.bl_label == 'Blackbody']:
                    smblnode.inputs[0].default_value = 2000 + 3500*sin(beta)**0.5 if beta > 0 else 2000
            if skysphere and not skysphere.hide and skysphere.data.materials[0].node_tree:
                if 'Sky Texture' in [no.bl_label for no in skysphere.data.materials[0].node_tree.nodes]:
                    skysphere.data.materials[0].node_tree.nodes['Sky Texture'].sun_direction = sin(phi), -cos(phi), sin(beta)

        sun['solhour'], sun['solday'], sun['soldistance'] = scene.solhour, scene.solday, scene.soldistance
    else:
        return

def epwlatilongi(scene, node):
    with open(node.weather, "r") as epwfile:
        fl = epwfile.readline()
        latitude, longitude = float(fl.split(",")[6]), float(fl.split(",")[7])
#    else:
#        latitude, longitude = node.latitude, node.longitude
    return latitude, longitude

#Compute solar position (altitude and azimuth in degrees) based on day of year (doy; integer), local solar time (lst; decimal hours), latitude (lat; decimal degrees), and longitude (lon; decimal degrees).
def solarPosition(doy, lst, lat, lon):
    #Set the local standard time meridian (lsm) (integer degrees of arc)
    lsm = round(lon/15, 0)*15
    #Approximation for equation of time (et) (minutes) comes from the Wikipedia article on Equation of Time
    b = 2*pi*(doy-81)/364
    et = 9.87 * sin(2*b) - 7.53 * cos(b) - 1.5 * sin(b)
    #The following formulas adapted from the 2005 ASHRAE Fundamentals, pp. 31.13-31.16
    #Conversion multipliers
    degToRad = 2*pi/360
    radToDeg = 1/degToRad
    #Apparent solar time (ast)
    ast = lst + et/60 + (lsm-lon)/15
    #Solar declination (delta) (radians)
    delta = degToRad*23.45 * sin(2*pi*(284+doy)/365)
    #Hour angle (h) (radians)
    h = degToRad*15 * (ast-12)
     #Local latitude (l) (radians)
    l = degToRad*lat
    #Solar altitude (beta) (radians)
    beta = asin(cos(l) * cos(delta) * cos(h) + sin(l) * sin(delta))
    #Solar azimuth phi (radians)
    phi = acos((sin(beta) * sin(l) - sin(delta))/(cos(beta) * cos(l)))
    #Convert altitude and azimuth from radians to degrees, since the Spatial Analyst's Hillshade function inputs solar angles in degrees
    altitude = radToDeg*beta
    phi = 2*pi - phi if ast<=12 or ast >= 24 else phi
    azimuth = radToDeg*phi
    return([altitude, azimuth, beta, phi])

def set_legend(ax):
    l = ax.legend(borderaxespad = -4)
    plt.setp(l.get_texts(), fontsize=8)

def wr_axes():
    fig = plt.figure(figsize=(8, 8), dpi=150, facecolor='w', edgecolor='w')
    rect = [0.1, 0.1, 0.8, 0.8]
    ax = WindroseAxes(fig, rect, axisbg='w')
    fig.add_axes(ax)
    return(fig, ax)

def vcframe(pp, scene, oblist, anim):
    for frame in range(scene.fs, scene.fe + 1):
        scene.frame_set(frame)
        for ob in oblist:
            if not ob.get('lires'):
                for vc in ob.data.vertex_colors:
                    vc.active = vc.active_render = vc.name == pp+str(frame)
                    vc.keyframe_insert("active")
                    vc.keyframe_insert("active_render")
            elif scene.vi_disp_3d == 1:
                for shape in ob.data.shape_keys.key_blocks:
                    if shape.name.isdigit():
                        shape.value = shape.name == str(frame)
                        shape.keyframe_insert("value")

def gentarget(tarnode, result):
    if tarnode.stat == '0':
        res = sum(result)/len(result)
    elif tarnode.stat == '1':
        res = max(result)
    elif tarnode.stat == '2':
        res = min(result)
    elif tarnode.stat == '3':
        res = sum(result)

    if tarnode.value > res and tarnode.ab == '0':
        return(1)
    elif tarnode.value < res and tarnode.ab == '1':
        return(1)
    else:
        return(0)

def selobj(scene, geo):
    for ob in scene.objects:
        ob.select = True if ob == geo else False
    scene.objects.active = geo

def nodeid(node, ngs):
    for ng in ngs:
        if node in ng.nodes[:]:
            return node.name+'@'+ng.name

def nodecolour(node, prob):
    (node.use_custom_color, node.color) = (1, (1.0, 0.3, 0.3)) if prob else (0, (1.0, 0.3, 0.3))
    return not prob

def remlink(node, links):
    for link in links:
        bpy.data.node_groups[node['nodeid'].split('@')[1]].links.remove(link)

def epentry(header, params, paramvs):
    return '{}\n'.format(header+(',', '')[header == ''])+'\n'.join([('    ', '')[header == '']+'{:{width}}! - {}'.format(str(pv[0])+(',', ';')[pv[1] == params[-1]], pv[1], width = s + (0, 4)[header == '']) for pv in zip(paramvs, params)]) + ('\n\n', '')[header == '']

def sockhide(node, lsocknames):
    try:
        for ins in [insock for insock in node.inputs if insock.name in lsocknames]:
            node.outputs[ins.name].hide = True if ins.links else False
        for outs in [outsock for outsock in node.outputs if outsock.name in lsocknames]:
            node.inputs[outs.name].hide = True if outs.links else False
    except Exception as e:
        print(e)

def socklink(sock, ng):
    try:
        for link in sock.links:
            lsock = (link.from_socket, link.to_socket)[sock.is_output]
            if sock.is_linked and sock.draw_color(bpy.context, sock.node) != lsock.draw_color(bpy.context, lsock.node):
                bpy.data.node_groups[ng].links.remove(link)
    except:
        pass

def epschedwrite(name, stype, ts, fs, us):
    print(ts, fs, us)
    params = ['Name', 'Schedule Type Limits Name']
    paramvs = [name, stype]
    for t in range(len(ts)):
        params.append('Field {}'.format(len(params)-2))
        paramvs .append(ts[t])
        for f in range(len(fs[t])):
            params.append('Field {}'.format(len(params)-2))
            paramvs.append(fs[t][f])
            for u in range(len(us[t][f])):
                params.append('Field {}'.format(len(params)-2))
                paramvs.append(us[t][f][u][0])
    return epentry('Schedule:Compact', params, paramvs)
    
def non_block_read(output):
    fd = output.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    try:
        return output.read()
    except:
        return ""