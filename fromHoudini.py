def parse_camera(scene, bobject, node):
    """As the name says."""
    import hou, math
    bobject['id']       = id_from_path(node.path())
    bobject['name']     = unicode(node.name())
    bobject['position'] = list(node.worldTransform().extractTranslates())
    bobject['target']   = list(hou.Vector3(0,0,-1) * node.worldTransform())
    aperture            = node.parm("aperture").eval()
    focal               = node.parm("focal").eval()
    bobject['fov']      = 2 * math.atan((aperture/2.0) / focal)
    return bobject

def parse_light(scene, bobject, node):
    """As name says. Point, spot, and distante light are suppored.
    """
    light_type = node.parm('light_type').eval()

    if light_type == 0:
        if node.parm('coneenable').eval():
            light_type = 2
    elif light_type == 6:
            light_type = 1
    else:
        light_type = 0

    bobject['type']     = light_type
    bobject['id']       = id_from_path(node.path())
    bobject['name']     = unicode(node.name())
    bobject['position'] = list(node.worldTransform().extractTranslates())
    bobject['direction']= list(node.worldTransform().extractRotates())
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

def parse_vertex_attribs(geometry, ignore_uv=False, duplicate_uv=False):
    """Parses vertices' attribs by iterating over polygons and its vertices.
    """

    positions = []
    normals   = []
    uvs       = []
    indices   = []

    for prim in geometry.prims():
        pr_num = prim.number()
        for v in prim.vertices():
            # NOTE: We need duplicate positions for vertices' attributes:
            pos = list(v.point().position())
            nor = list(v.attribValue("N"))
            if not ignore_uv:
                if not duplicate_uv:
                    uv = list(v.attribValue('uv'))
                else:
                    uv = list(v.point().attribValue('uv'))
                uvs += uv[:-1]
            idx = (3 * pr_num) + v.number()
            positions += pos
            normals   += nor
            indices.append(idx)

    return positions, normals, uvs, indices
    

def define_submesh(submesh, positions, indices, materialIndex=0, 
                    verticesStart=0, indexStart=0):
    submesh['materialIndex'] = materialIndex
    submesh['verticesStart'] = verticesStart
    submesh['verticesCount'] = len(positions) / 3
    submesh['indexStart']    = indexStart
    submesh['indexCount']    = len(indices)
    return submesh


def parse_sop(scene, bobject, sop):
    """Parse SOP geometry for attributes suppored by Babylon. Two paths seem to be necesery, 
    as we apparantly can't mix point's and vertex arrays. That is either all arrays hold 
    data per vertex or per point. The latter one is more efficent for us.
    TODO: Support uv2, color 
    """
    geometry  = sop.geometry()
    positions = []
    indices   = []
    normals   = []
    uvs       = []
    import hou
    # Check if we have vertex' or points's defined attributes:
    if geometry.findVertexAttrib("N"):
        ignore_uv = True if not geometry.findVertexAttrib('uv') \
        and not geometry.findPointAttrib('uv') else False
        duplicate_uv = not geometry.findVertexAttrib('uv')
        positions, normals, uvs, indices = parse_vertex_attribs(\
            geometry, ignore_uv, duplicate_uv)

    # Aternatively use point attribs (faster!)
    else:
        if geometry.findPointAttrib('N'):
            normals = list(geometry.pointFloatAttribValues('N'))
        else:
            # NOTE: eearly quit as it seams that Babylon can't deal with 
            # geometry without normals.
            return bobject

        if geometry.findPointAttrib('uv'):
            uvs = list(geometry.pointFloatAttribValues('uv'))

        positions = list(geometry.pointFloatAttribValues('P'))

        # We need only indices now:
        # TODO: Can it be faster without inlinec++?
        # Maybe vex preprocess?
        for prim in geometry.prims():
            for v in prim.vertices():
                indices.append(v.point().number())

    # Assign arrays to our object:
    # TODO: I would rather use vertexData if possible.
    bobject['positions'] = positions
    bobject['normals']   = normals
    bobject['uvs']       = uvs
    bobject['indices']   = indices

    submesh = scene.new('subMesh')
    submesh = define_submesh(submesh, positions, indices)
    bobject['subMeshes'].append(submesh)

    return bobject


def parse_obj(scene, bobject, node):
    """ Creates a babylon mesh from Obj node.
    """
    transform  = node.worldTransform().extractTranslates()
    rotation   = node.worldTransform().extractRotates()
    scale      = node.worldTransform().extractScales()
    bobject['id']       = id_from_path(node.path())
    bobject['name']     = unicode(node.name())
    bobject['position'] = list(transform)
    bobject['rotation'] = list(rotation)
    bobject['scaling']  = list(scale)
    return bobject

def parse_material(scene, bobject, shop):
    """Find usual Mantra parameters on usual shaders and tries to map it
       to Babylon material.
    """
    import os.path
    def getparmv(bobject, d, shop, s):
        """FIXME: This needs more work. Str versus digits etc.
        """
        if s in shop.parms() and d in bobject.keys():
            v = list(shot.parmTuple(s).eval())
            if len(v) == 1:
                return v[0]
            return v
        else:
            return bobject[d]

    bobject['id']            = id_from_path(shop.path())
    bobject['name']          = unicode(shop.name())
    bobject['diffuse']       = getparmv(bobject, 'diffuse', shop, 'baseColor')
    bobject['specular']      = getparmv(bobject, 'specular', shop, 'specColor1')
    bobject['specularPower'] = getparmv(bobject, 'specularPower', shop, 'spec_rough' )
    diffuseTexture           = scene.new('diffuseTexture')
    diffuseTexture['name']   = unicode(os.path.split(shop.parm('baseColorMap').eval())[1])
    bobject['diffuseTexture'] = diffuseTexture
    return bobject

def id_from_path(path):
    return unicode(path.replace("/", "_")[1:])

def run(scene, selected):
    """Callback of Houdini's shelf.
    """
    import hou
    for node in selected:
        if node.type().name() == "cam":
            camera = parse_camera(scene, scene.new("camera"), node)
            scene.add(camera)

        elif node.type().name() == "hlight":
            light  = parse_light(scene, scene.new("light"), node)
            # TODO: Move to to parser:
            shadow = scene.new("shadowGenerator")
            shadow['lightId'] = light['id']
            scene.add(shadow)
            scene.add(light)

        elif node.type().name() == 'geo':
            # Babylon mesh is Houdini's Obj, and babylon geometry/vertexData
            # is closer to Houdini's SOPs. NOTE: We send to the parsers the same 
            # object twise just changing its name (mesh->obj), so Mesh will keep 
            # both geometry and object data.
            mesh  = parse_sop(scene, scene.new('mesh'), node.renderNode())
            obj   = parse_obj(scene, mesh, node)
            # Obj level materials for now:
            material_path = node.parm('shop_materialpath').eval()
            if material_path != "":
                material = parse_material(scene, scene.new('material'), hou.node(material_path))
                obj['materialId'] = material['id']
                scene.add(material)
            scene.add(obj)

    # link shadows:
    for mesh in scene['meshes']:
        for shadow in scene['shadowGenerators']:
            if mesh['id'] not in shadow['renderList']:
                shadow['renderList'].append(mesh['id'])

    scene.dump("/Users/symek/Documents/work/habylon/test.babylon")
    scene.dump("/Users/symek/Sites/test.babylon")
    return scene
