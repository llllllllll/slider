from abc import ABCMeta, abstractmethod
from hashlib import md5
import os

from .beatmap import Beatmap


class Library(metaclass=ABCMeta):
    """A collection of beatmaps.
    """
    @abstractmethod
    def lookup_by_id(self, beatmap_id):
        """Retrieve a beatmap by its beatmap id.

        Parameters
        ----------
        beatmap_id : int
            The id of the beatmap to lookup.

        Returns
        -------
        beatmap : Beatmap
            The beatmap with the given id.

        Raises
        ------
        KeyError
            Raised when the given id is not in the library.
        """
        raise NotImplementedError('lookup_by_id')

    @abstractmethod
    def lookup_by_md5(self, beatmap_md5):
        """Retrieve a beatmap by its md5 hash.

        Parameters
        ----------
        beatmap_md5 : bytes
            The md5 hash of the beatmap to lookup.

        Returns
        -------
        beatmap : Beatmap
            The beatmap with the given md5 hash.

        Raises
        ------
        KeyError
            Raised when the given md5 hash is not in the library.
        """
        raise NotImplementedError('lookup_by_md5')

    @classmethod
    def __init_subclass__(cls):
        # copy docstring down for abstract methods
        for name, method in vars(__class__).items():  # noqa
            if not getattr(method, '__isabstract__', False):
                continue

            implementation = getattr(cls, name, None)
            if implementation is None or implementation.__doc__ is not None:
                continue

            implementation.__doc__ = method.__doc__


class LocalLibrary(Library):
    """A library backed by a local directory.

    Parameters
    ----------
    path : str or pathlib.Path
        The path to a directory of ``.osu`` files.
    """
    def __init__(self, path):
        self._by_id = by_id = {}
        self._by_md5 = by_md5 = {}
        for entry in os.scandir(path):
            if not entry.name.endswith('.osu'):
                continue

            with open(entry, 'rb') as f:
                data = f.read()

            try:
                beatmap = Beatmap.parse(data.decode('utf-8-sig'))
            except ValueError as e:
                raise ValueError(f'failed to parse {entry.path}') from e

            by_md5[md5(data).hexdigest()] = beatmap

            beatmap_id = beatmap.beatmap_id
            if beatmap_id is not None:
                # very old beatmaps didn't store the id in the ``.osu`` file
                by_id[beatmap_id] = beatmap

    def lookup_by_id(self, beatmap_id):
        return self._by_id[beatmap_id]

    def lookup_by_md5(self, beatmap_md5):
        return self._by_md5[beatmap_md5]
