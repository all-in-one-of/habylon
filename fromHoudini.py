def parse_camera(bobject, node):
    """As the name says."""
    import hou, math
    bobject['id']       = unicode(node.name())
    bobject['name']     = unicode(node.name())
    bobject['position'] = list(node.parmTuple('t').eval())
    bobject['target']   = list(hou.Vector3(0,0,-1) * node.worldTransform())
    aperture            = node.parm("aperture").eval()
    focal               = node.parm("focal").eval()
    bobject['fov']      = 2 * math.atan((aperture/2.0) / focal)
    return bobject

def parse_light(bobject, node):
    """As name says. Point, spot, and distante light are suppored."""
    light_type = node.parm('light_type').eval()
    if light_type == 0:
        if node.parm('coneenable').eval():
            light_type = 2
    elif light_type == 6:
            light_type = 1
    else:
        light_type = 0

    bobject['type']     = light_type
    bobject['position'] = list(node.parmTuple('l_t').eval())
    bobject['direction']= list(node.parmTuple('l_r').eval())
    bobject['diffuse']  = list(node.parmTuple('light_color').eval())
    bobject['intensity']= node.parm('light_intensity').eval()
    return bobject

def parse_geo_as_bbox(bobject, node):
    """From box from bounding box of a geometry.
    This is place holder for time we will have polygon
    parser.
    """
    geo    = node.renderNode().geometry()
    bbox   = geo.boundingBox()
    bobject['size'] = bbox.sizevec()[0]
    bobject['id']   = unicode(node.name())
    return bobject

def parse_geo(bobject, node):
    """Parse polygons (triangles with mandatory uv and N attribs).
    """
    geo = node.renderNode().geometry()
    # points = list(geo.pointFloatAttribValues("P"))
    positions = []
    normals   = []
    uvs       = []
    indices   = []

    for prim in geo.prims():
        num = prim.number()
        for v in prim.vertices():
            pos = list(v.point().position())
            nor = list(v.attribValue("N"))
            uv  = list(v.attribValue('uv'))
            idx = (3*num) + v.number()
            positions += pos
            normals   += nor
            uvs       += uv[:-1]
            indices.append(idx)
    
    bobject['positions'] = positions
    bobject['normals']   = normals
    bobject['uvs']       = uvs
    bobject['indices']   = indices

    return bobject

def parse_obj(bobject, node):
    """ Creates a babylon mesh from geo node.
    """
    transform  = node.worldTransform().extractTranslates()
    rotation   = node.worldTransform().extractRotates()
    scale      = node.worldTransform().extractScales()
    bobject['id']       = unicode(node.name())
    bobject['name']     = unicode(node.name())
    bobject['position'] = list(transform)
    bobject['rotation'] = list(rotation)
    bobject['scaling']  = list(scale)
    return bobject

def run(scene, selected):
    """Callback of Houdini's shelf.
    """
    for node in selected:
        if node.type().name() == "cam":
            camera = parse_camera(scene.new("camera"), node)
            scene.add(camera)
        elif node.type().name() == "hlight":
            light = parse_light(scene.new("light"), node)
            scene.add(light)
        elif node.type().name() == 'geo':
            geo  = parse_geo(scene.new('mesh'), node)
            mesh = parse_obj(geo, node)
            # mesh['geometryId'] = geo['id']
            scene.add(mesh)
            # scene.add(geo)

    scene.dump("/Users/symek/Documents/work/habylon/test.babylon")
    scene.dump("/Users/symek/Sites/test.babylon")
    return scene
