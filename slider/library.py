from abc import ABCMeta, abstractmethod
from functools import lru_cache
from hashlib import md5
import os

from requests import HTTPError

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

    @property
    def beatmaps(self):
        return self._by_md5.values()


class ClientLibrary(Library):
    """A library backed by a :class:`~slider.client.Client`. This can fetch
    any beatmap that exists on the osu! servers.

    Parameters
    ----------
    client : Client
        The osu! client to use when downloading beatmaps.
    cache : int, optional
        The amount of beatmaps to cache in memory. This uses
        :func:`functools.lru_cache`, and if set to None will cache everything.
    """
    def __init__(self, client, cache=2048):
        self.client = client
        self._download_beatmap = lru_cache(cache)(self._raw_download_beatmap)

    def _raw_download_beatmap(self, *, beatmap_id=None, beatmap_md5=None):
        """Function for downloading beatmaps from the osu! website.

        This handles both cases to only require a single lru cache.
        """
        try:
            if beatmap_id is not None:
                return self.client.beatmap(beatmap_id=beatmap_id).beatmap

            return self.client.beatmap(beatmap_md5=beatmap_md5).beatmap
        except HTTPError:
            raise KeyError(
                beatmap_id if beatmap_id is not None else beatmap_md5,
            )

    def lookup_by_id(self, beatmap_id):
        return self._download_beatmap(beatmap_id=beatmap_id)

    def lookup_by_md5(self, beatmap_md5):
        return self._download_beatmap(beatmap_md5=beatmap_md5)


class ChainedLibrary(Library):
    """A library that tries to read from multiple libraries in priority order.

    Parameters
    ----------
    *libraries
        The libraries to read from in the order to search.
    """
    def __init__(self, *libraries):
        self.libraries = libraries

    def lookup_by_id(self, beatmap_id):
        for library in self.libraries:
            try:
                return library.lookup_by_id(beatmap_id)
            except KeyError:
                pass
        raise KeyError(beatmap_id)

    def lookup_by_md5(self, beatmap_md5):
        for library in self.libraries:
            try:
                return library.lookup_by_md5(beatmap_md5)
            except KeyError:
                pass
        raise KeyError(beatmap_md5)
