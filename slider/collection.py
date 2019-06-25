# TODO: not use replay private functions
from .replay import _consume_int, _consume_string


class CollectionDB:
    def __init__(self, version, num_collections, collections):
        self.version = version
        self.num_collections = num_collections
        self.collections = collections

    @classmethod
    def from_path(cls, path):
        with open(path, 'rb') as f:
            return cls.from_file(f)

    @classmethod
    def from_file(cls, file):
        return cls.parse(file.read())

    @classmethod
    def parse(cls, data):
        buffer = bytearray(data)

        version = _consume_int(buffer)
        num_collections = _consume_int(buffer)
        collections = []
        for i in range(num_collections):
            collections.append(Collection.parse(buffer))

        return cls(version, num_collections, collections)


class Collection:
    def __init__(self, name, num_beatmaps, md5_hashes):
        self.name = name
        self.num_beatmaps = num_beatmaps
        self.md5_hashes = md5_hashes

    @classmethod
    def parse(cls, buffer):
        name = _consume_string(buffer)
        num_beatmaps = _consume_int(buffer)
        md5_hashes = []
        for i in range(num_beatmaps):
            md5_hashes.append(_consume_string(buffer))

        return cls(name, num_beatmaps, md5_hashes)
