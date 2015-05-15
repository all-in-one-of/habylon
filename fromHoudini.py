def parse_camera(scene, bobject, node):
    """As the name says."""
    from hou import Vector3, Matrix4
    from math import atan

    babylonTransform    = convert_space(node.worldTransform(), \
                                        scene.HOUDINI_TO_BABYLON_SPACE)
    bobject['id']       = id_from_path(node.path())
    bobject['name']     = unicode(node.name())
    bobject['position'] = list(babylonTransform.extractTranslates())
    bobject['target']   = list(Vector3(0,0,-1) * babylonTransform)
    aperture            = node.parm("aperture").eval()
    focal               = node.parm("focal").eval()
    bobject['fov']      = 2 * atan((aperture/2.0) / focal)
    return bobject


def convert_space(matrix, space):
    """ Convert between different coordinate system using provided
        matrix.
    """
    from hou import Matrix4
    new_space = Matrix4(space)
    return new_space.inverted() * matrix * new_space

def parse_light(scene, bobject, node):
    """As name says. Point, spot, and distante light are supported.
    """
    from hou import Vector3, Matrix4

    light_type = node.parm('light_type').eval()
    if light_type == 0:
        if node.parm('coneenable').eval():
            light_type = 2
    elif light_type == 6:
            light_type = 1
    else:
        light_type = 0

    babylonTransform    = convert_space(node.worldTransform(), \
                                        scene.HOUDINI_TO_BABYLON_SPACE)
    bobject['type']     = light_type
    bobject['id']       = id_from_path(node.path())
    bobject['name']     = unicode(node.name())
    bobject['position'] = list(babylonTransform.extractTranslates())
    # Similarly to camera, Houdini's lights have flipped z axis:
    bobject['direction']= list(Vector3(0,0,-1) * babylonTransform)
    bobject['diffuse']  = list(node.parmTuple('light_color').eval())
    bobject['intensity']= node.parm('light_intensity').eval()
    #FIXME: JS examples claims this should be in radians, but makes no sense in tests...
    bobject['angle']    = node.parm('coneangle').eval()
   
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
        TODO: This will be terribly slow for many/big meshes.
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


def parse_sop(scene, bobject, sop, binary=False):
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
    uvs2      = []
    colors    = []
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
            # NOTE: early quit as it seams that Babylon can't deal with 
            # geometry without normals.
            return bobject

        # Uvs:
        if geometry.findPointAttrib('uv'):
            uvs = list(geometry.pointFloatAttribValues('uv'))
        # Uvs2:
        if geometry.findPointAttrib('uv2'):
            uvs2 = list(geometry.pointFloatAttribValues('uv2'))

        # Color:
        # TODO: add alpha per point:
        if geometry.findPointAttrib('Cd'):
            colors = list(geometry.pointFloatAttribValues('Cd'))

        positions = list(geometry.pointFloatAttribValues('P'))

        # We need only indices now:
        # TODO: Can it be faster without inlinec++?
        # Maybe vex preprocess?
        for prim in geometry.prims():
            for v in prim.vertices():
                indices.append(v.point().number())

    # Assign arrays to our object using vertexData
    # and assigning it to this mesh.
    # TODO: I assume vertexData could be shared among meshes. Can we support it?
    # This would be possible via packed primitive assuming we can recongize them
    # via an attribute (check).

    # User either vertexData object to hold geometry
    # or convert arrays to binary string, which we should
    # save to file later on.
    if not binary:
        # FIXME: This isn't clean...
        vertexData = scene.new('vertexData')
        vertexData['id'] = id_from_path(sop.path())
        bobject['geometryId'] = vertexData['id']
        scene.add(vertexData)
        bobject.__delitem__('delayLoadingFile')
        bobject.__delitem__('_binaryInfo')
        data_holder = vertexData
    else:
        data_holder = bobject

    # data_holder is either vertexData or mesh object
    # depending whether we want save data to binary format (the latter case)
    data_holder['positions'] = positions
    data_holder['normals']   = normals
    data_holder['uvs']       = uvs
    data_holder['uvs2']      = uvs2
    data_holder['colors']    = colors
    data_holder['indices']   = indices

    # We have to remove this key, otherwise Bab. will see black color:
    if not colors:
        data_holder.__delitem__('colors')


    submesh = scene.new('subMesh')
    submesh = define_submesh(submesh, positions, indices)
    bobject['subMeshes'].append(submesh)
    scene.add(bobject)

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
    # TODO: Not sure it this is right place for bounding box retrival.
    geometry = node.renderNode().geometry()
    bobject['boundingBoxMinimum'] = list(geometry.boundingBox().minvec())
    bobject['boundingBoxMaximum'] = list(geometry.boundingBox().maxvec())
    return bobject

def parse_material(scene, bobject, shop):
    """Find usual Mantra parameters on usual shaders and tries to map it
       to Babylon material.
    """
    import os.path
    def getparmv(shop, s, bobject=None, d=None):
        """FIXME: This needs more work. Str versus digits etc.
        """
        if s in shop.parms():
            v = list(shot.parmTuple(s).eval())
            if len(v) == 1:
                return v[0]
            return v
        else:
            if d and bobject:
                if d in bobject.keys():
                    return bobject[d]

    def multVec(vec, m):
        """Basic vec multiplier"""
        vec = list(vec)

        if type(m) in (type(0), type(0.0)):
            return [x*m for x in vec]
        else:
            m = list(m)
            return [x*y for x, y in zip(vec, m)]


    bobject['id']            = id_from_path(shop.path())
    bobject['name']          = unicode(shop.name())
    bobject['diffuse']       = list(multVec(shop.parmTuple("baseColor").eval(), \
                                            shop.parm("diff_int").eval()))
    bobject['specular']      = list(multVec(shop.parmTuple("specColor1").eval(),\
                                            shop.parm("spec_int").eval()))
    bobject['specularPower'] = getparmv(shop, 'spec_rough', bobject, 'specularPower')

    # Maps:
    if shop.parm("useColorMap").eval():
        diffuseTexture           = scene.new('texture')
        diffuseTexture['name']   = unicode(os.path.split(shop.parm('baseColorMap').eval())[1])
        bobject['diffuseTexture']= diffuseTexture
    if shop.parm("useNormalMap").eval():
        # Babylon bump map is actually normal map...
        bumpTexture              = scene.new('texture')
        bumpTexture['name']      = unicode(os.path.split(shop.parm('baseNormalMap').eval())[1])
        bobject['bumpTexture']   = bumpTexture


    return bobject

def parse_channels(scene, bobject, node, parm, start, end,  freq=30):
    """ Parse animated parameters on Obj level. freq is frequence we evaluate channels
        defined by expressions, (not keyframes). Still I don't know what to do if parmTuple
        have channels in different frames. 
    """
    keyframes = []
    #FIXME: This doesn't account for cases when object is pareted to animated source,
    # We could check worldTransform(), but this wouldn't be efficent to bake any animation 
    # per frame, would it? Perhaps this should be an user option?
    # FIXME: Not sure if this should be here. parser shouldn't be worry about
    # targets name or whatevert else... just parse object and return values!
    channels  = {"t": u"position", 'r': u'rotation', 's': u"scaling"}
    bobject['name']     = id_from_path(node.path()) + "_" + channels[parm[0]]
    bobject['property'] = channels[parm[0]]
    bobject['dataType'] = scene.ANIM_TYPE_VECTOR

    # Find and parse keyframes. 
    # NOTE: First keys found determins other channels values in parmTuple
    parm = node.parm(parm)
    # NOTE: we assume for now that single keyframe means expression...
    if len(parm.keyframes()) > 1:
        for item in parm.keyframes():
            keyframe = scene.new('animationKey')
            keyframe['frame']  = item.frame()
            keyframe['values'] = list(parm.tuple().evalAsFloatsAtFrame(item.frame()))
            bobject['keys'].append(keyframe)
    else:
    # Single keyframe makes channel to bake. 
    # This definitely should be exporter option per object.
        for frame in range(start, end, freq):
            keyframe = scene.new("animationKey")
            keyframe['frame']  = frame * 1.0
            keyframe['values'] = list(parm.tuple().evalAsFloatsAtFrame(int(frame)))
            bobject['keys'].append(keyframe)

    first = bobject['keys'][0]['frame']
    last  = bobject['keys'][-1]['frame']
    bobject['autoAnimateFrom'] = first 
    bobject['autoAnimateTo']   = last

    return bobject

def convert_to_binary(scene, mesh):
    """ Converts provided Mesh object into babylon binary format, 
        and saves it to path location.
    """
    # For starter. TODO: add colors, uvs2:
    binary_attributes =  (('positions', 3, scene.BINARY_DATA_FLOAT), 
                          ('normals',   3, scene.BINARY_DATA_FLOAT), 
                          ('uvs',       2, scene.BINARY_DATA_FLOAT),  
                          ('indices',   1, scene.BINARY_DATA_INT))

    binaryStr = ""
    offset    = 0
    binaryInfo = scene.new('_binaryInfo')

    for attribName, stride, _type in binary_attributes:
        attribArray = mesh[attribName]
        # Attribute == []:
        if not attribArray:
            continue
        # otherwise convert and concatenate:
        binaryStr  += scene.to_binary_string(attribArray)
        binaryInfo["%sAttrDesc"%attribName] = \
        {'count': len(attribArray), 'stride': stride, 'offset': offset, 'dataType': _type}
        # Offset in bytes, it seems both floats and int are 4bytes long: 
        offset += len(attribArray)*4
        # Remove data from mesh:
        mesh[attribName] = []

    # last x5 ints are subMeshesInfo:
    for submesh in mesh['subMeshes']:
        _array = [submesh["materialIndex"], submesh["verticesStart"], 
                  submesh["indexCount"], submesh["indexStart"], submesh["verticesCount"]]
        binaryStr += scene.to_binary_string(_array)

    binaryInfo['subMeshesAttrDesc'] = \
    {'count': len(mesh['subMeshes']), 'stride': 5, 'offset': offset, 'dataType': 0}

    mesh['_binaryInfo']      = binaryInfo
    mesh['delayLoadingFile'] = mesh['id'] + ".binary.babylon"
    return mesh, binaryStr


def id_from_path(path):
    """Just a pretty-look id from Houdini's object path.
    """
    return unicode(path.replace("/", "_")[1:])

def run(scene, selected, binary=False, scene_save_path="/var/www/html/"):
    """Callback of Houdini's shelf.
    """
    import hou
    import os
    for node in selected:
        if node.type().name() == "cam":
            camera = parse_camera(scene, scene.new("camera"), node)
            scene.add(camera)

        elif node.type().name() == "hlight":
            light  = parse_light(scene, scene.new("light"), node)
            # shadow_type = 0 means no shadow, else raytrace or depth shadows:
            if node.parm('shadow_type').eval():
                shadow = scene.new("shadowGenerator")
                shadow['lightId'] = light['id']
                scene.add(shadow)
            scene.add(light)

        elif node.type().name() == 'geo':
            # Babylon mesh is Houdini's Obj, and babylon geometry/vertexData
            # is closer to Houdini's SOPs. NOTE: We send to the parsers the same 
            # object twise just changing its name (mesh->obj), so Mesh will keep 
            # both geometry and object data.

            # Parse object level properties:
            obj   = parse_obj(scene, scene.new('mesh'), node)
            print obj
            mesh  = parse_sop(scene, obj, node.renderNode(), binary)

            # Binary format: 
            if binary:
                mesh, bin = convert_to_binary(scene, mesh)
                filename  = mesh['id'] + ".binary.babylon"
                with open(os.path.join(scene_save_path, filename), 'wb') as file: 
                    file.write(bin)


            # Obj level materials for now:
            material_path = node.parm('shop_materialpath').eval()
            if material_path != "":
                material = parse_material(scene, scene.new('material'), hou.node(material_path))
                obj['materialId'] = material['id']
                scene.add(material)

            # Animation export. Babylon deals with vector or float animation,
            # so we have to treat all tuple channeles at once even if only one axe
            # is animated.
            for tuple_ in "t r s".split():
                for axe in 'x y z'.split():
                    parm = tuple_ + axe
                    if node.parm(parm).isTimeDependent():
                        start, end = (hou.expandString("$RFSTART"), hou.expandString('$RFEND'))
                        animation = parse_channels(scene, scene.new('animation'), node, parm, int(start), int(end), int(hou.fps()))
                        obj['animations'].append(animation)
                        break


            scene.add(obj)

    # link shadows:
    # TODO: Respect shadow linking. 
    for shadow in scene['shadowGenerators']:
        for mesh in scene['meshes']:
            if mesh not in shadow['renderList']:
                shadow['renderList'].append(mesh['id'])

    scene.dump(os.path.join(scene_save_path, "test.babylon"))
    return scene
