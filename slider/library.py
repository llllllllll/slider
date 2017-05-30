import dbm
from functools import lru_cache
from hashlib import md5
import os
import pathlib

import requests

from .beatmap import Beatmap


class Library:
    """A library of beatmaps backed by a local directory.

    Parameters
    ----------
    path : path-like
        The path to a local library directory.
    cache : int, optional
        The amount of beatmaps to cache in memory. This uses
        :func:`functools.lru_cache`, and if set to None will cache everything.
    download_url : str, optional
        The default location to download beatmaps from.
    """
    DEFAULT_DOWNLOAD_URL = 'https://osu.ppy.sh/osu'
    DEFAULT_CACHE_SIZE = 2048

    def __init__(self,
                 path,
                 *,
                 cache=DEFAULT_CACHE_SIZE,
                 download_url=DEFAULT_DOWNLOAD_URL):
        self.path = path = pathlib.Path(path)
        self._cache = dbm.open(str(path / '.db'), 'c')
        self._read_beatmap = lru_cache(cache)(self._raw_read_beatmap)
        self._download_url = download_url

    def close(self):
        """Close any resources used by this library.
        """
        self._read_beatmap.cache_clear()
        self._cache.close()

    __del__ = close

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    @classmethod
    def create_db(cls,
                  path,
                  *,
                  cache=DEFAULT_CACHE_SIZE,
                  download_url=DEFAULT_DOWNLOAD_URL):
        """Create a Library from a directory of ``.osu`` files.

        Parameters
        ----------
        path : path-like
            The path to the directory to read.
        cache : int, optional
            The amount of beatmaps to cache in memory. This uses
            :func:`functools.lru_cache`, and if set to None will cache
            everything.
        download_url : str, optional
            The default location to download beatmaps from.
        """
        self = cls(path)
        save = self.save

        for entry in os.scandir(path):
            path = entry.path
            if not path.endswith('.osu'):
                continue

            with open(path, 'rb') as f:
                data = f.read()

            try:
                save(data, path)
            except ValueError as e:
                raise ValueError(f'failed to save {entry.path}') from e

        return self

    @staticmethod
    def _raw_read_beatmap(self, *, beatmap_id=None, beatmap_md5=None):
        """Function for opening beatmaps from disk.

        This handles both cases to only require a single lru cache.

        Notes
        -----
        This is a ``staticmethod`` to avoid a cycle from self to the lru_cache
        back to self.
        """
        if beatmap_id is not None:
            return Beatmap.from_path(self._cache[f'id:{beatmap_id}'])

        return Beatmap.from_path(self._cache[f'md5:{beatmap_md5}'])

    def lookup_by_id(self, beatmap_id, *, download=False, save=False):
        """Retrieve a beatmap by its beatmap id.

        Parameters
        ----------
        beatmap_id : int
            The id of the beatmap to lookup.

        Returns
        -------
        beatmap : Beatmap
            The beatmap with the given id.
        download : bool. optional
            Download the map if it doesn't exist.
        save : bool, optional
            If the lookup falls back to a download, should the result be saved?

        Raises
        ------
        KeyError
            Raised when the given id is not in the library.
        """
        try:
            return self._read_beatmap(self, beatmap_id=beatmap_id)
        except KeyError:
            return self.download(beatmap_id, save=save)

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
        return self._read_beatmap(self, beatmap_md5=beatmap_md5)

    def save(self, data, *, beatmap=None):
        """Save raw data for a beatmap at a given location.

        Parameters
        ----------
        data : bytes
            The unparsed beatmap data.
        beatmap : Beatmap, optional
            The parsed beatmap. If not provided, the raw data will be parsed.

        Returns
        -------
        beatmap : Beatmap
            The parsed beatmap.
        """
        if beatmap is None:
            beatmap = Beatmap.parse(data.decode('utf-8-sig'))

        cache = self._cache

        path = self.path / (
            f'{beatmap.artist} - '
            f'{beatmap.title} '
            f'({beatmap.creator})'
            f'[beatmap.version]'
            f'.osu'
        )
        with open(path, 'w') as f:
            f.write(data)

        cache[f'md5:{md5(data).hexdigest()}'] = path

        beatmap_id = beatmap.beatmap_id
        if beatmap_id is not None:
            # very old beatmaps didn't store the id in the ``.osu``
            # file
            cache[f'id:{beatmap_id}'] = path

        return beatmap

    def download(self, beatmap_id, *, save=False):
        """Download a beatmap.

        Parameters
        ----------
        beatmap_id : int
            The id of the beatmap to download.
        save : bool, optional
            Save the beatmap to disk?

        Returns
        -------
        beatmap : Beatmap
            The downloaded beatmap.
        """
        beatmap_response = requests.get(f'{self._download_url}/{beatmap_id}')
        beatmap_response.raise_for_status()

        data = beatmap_response.content
        beatmap = Beatmap.parse(data.decode('utf-8-sig'))

        if save:
            self.save(data, beatmap=beatmap)

        return beatmap
