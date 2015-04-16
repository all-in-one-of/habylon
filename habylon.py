import json
import os, sys
import glob
import collections

class BObject(dict):
    def __init__(self, schema, obj):
        super(BObject, self).__init__(schema[obj])
        self.type = obj
    def __setitem__(self, key, value):
        """Custom item setter. Main reason fo it is type checking.
        """
        assert key in self, "Key %s not defined in schema" % key
        if isinstance(value, type(self[key])):
            super(BObject, self).__setitem__(key, value)
        else:
            raise TypeError("Wrong type of %s: %s" % (key, value))
            
    def __repr__(self):
        from json import dumps
        return dumps(self, indent=1)

def load_schema(path):
    schema = {}
    schemas = os.path.join(path, "*.json")
    files   = glob.glob(schemas)

    for file in files:
        with open(file) as file_object:
            obj  = json.load(file_object)
            name = os.path.split(file)[1]
            name = os.path.splitext(name)[0]
            schema[name] = obj

    return schema


# Get recipe:
schema = load_schema("./schema")

# Scene instance:
scene = BObject(schema, 'scene')

# Mesh instance:
mesh = BObject(schema, "mesh") 

# Vertx buffer
vertices = BObject(schema, 'vertexData')

# Combine them:
scene['geometries']['vertexData'].append(vertices)
mesh['geometryId'] = vertices['id']
scene['meshes'].append(mesh)

print scene

# print json.dumps(scene, indent=2)