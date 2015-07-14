from document import Document, loader
import json


class Config(Document):
    schema = loader("config.schema")
    pk = None

    @classmethod
    def load(cls, fn):
        data = json.load(open(fn))
        return cls(data)
