from bson.json_util import loads, dumps
import datetime
import jsonschema
import pkg_resources
from tornado import gen


def loader(filename):
    fn = pkg_resources.resource_filename(__name__, filename)
    return loads(open(fn).read())


class Document(dict):
    def __init__(self, data=None):
        self.update(data)

    def __str__(self):
        return self.bson()

    def bson(self):
        return dumps(self)

    def validate(self):
        jsonschema.validate(self, self.schema)

    def __setitem__(self, key, value):
        self[key] = value
        self.validate()

    def update(self, data=None, **kwargs):
        if data:
            if isinstance(data, str):
                data = loads(data)
            super(Document, self).update(data)
        super(Document, self).update(kwargs)
        self.validate()

    @classmethod
    @gen.coroutine
    def load(cls, db, key):
        document = yield db.find_one({cls.pk: key})
        if document:
            raise gen.Return(cls(document))
        raise gen.Return(cls({cls.pk: key}))

    @classmethod
    def query_from_schema(cls, key, value):
        spec = cls.schema['properties'].get(key)
        if not spec:
            return {"$eq": value}
        stype = spec.get("type", "string")
        if stype == "number":
            return {"$eq": int(value)}
        return {"$regex": value}

    @classmethod
    @gen.coroutine
    def find(cls, db, **kwargs):
        query = {}
        for k, v in kwargs.items():
            query[k] = cls.query_from_schema(k, v)
        if not query:
            query = {cls.pk: {"$exists": True}}
        cursor = db.find(query)
        # XXX: how to only yield cls instances?
        result = []
        while (yield cursor.fetch_next):
            doc = cursor.next_object()
            result.append(cls(doc))
        raise gen.Return(result)

    @gen.coroutine
    def save(self, db, upsert=True):
        pk = self[self.pk]
        self.validate()
        dict.__setitem__(self, 'lastModified',
                         datetime.datetime.utcnow())
        yield db.update({self.pk: pk},
                        {'$set': self},
                        upsert=upsert)

    @gen.coroutine
    def remove(self, db):
        yield db.remove({self.pk: self[self.pk]})


class Interface(Document):
    schema = loader("interface.schema")
    pk = "id"


class Layer(Document):
    schema = loader("layer.schema")
    pk = "id"
