from bson.json_util import loads, dumps
import datetime
import jsonschema
import logging
import pkg_resources
from tornado import autoreload
from tornado import gen


def watcher(fn, watchset=set()):
    if fn not in watchset:
        autoreload.watch(fn)
        logging.debug("Autoreload: {}".format(fn))
        watchset.add(fn)


def loader(filename, watch=True):
    fn = pkg_resources.resource_filename(__name__, filename)
    if watch:
        watcher(fn)
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
    def load(cls, db, key, update=True):
        document = yield db.find_one({cls.pk: key})
        if document:
            raise gen.Return(cls(document))
        else:
            empty = cls.empty()
            empty.update({cls.pk: key})
            document = cls(empty)
        raise gen.Return(document)

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
    def empty(cls):
        """Return a dict populated with default (or empty) values from schema"""
        result = {}
        for k, v in cls.schema['properties'].items():
            value = v.get("default", None)
            if value is None:
                if v.get('type', 'string') == "string":
                    value = ""
            result[k] = value
        return result

    @classmethod
    @gen.coroutine
    def find(cls, db, sort=True, **kwargs):
        query = {}
        for k, v in kwargs.items():
            query[k] = cls.query_from_schema(k, v)
        if not query:
            query = {cls.pk: {"$exists": True}}

        query = {"$query": query}
        if sort:
            query["$orderby"] = {cls.pk: 1}

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
