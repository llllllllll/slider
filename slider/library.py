import dbm
from functools import lru_cache
from hashlib import md5
import os
import pathlib
from time import sleep
import sys

import requests

from .beatmap import Beatmap
from .cli import maybe_show_progress


class Cache:
    def __init__(self, path, overwrite):
        self.path = path
        if overwrite:
            dbm.open(str(self.path), 'n').close()

    @property
    def _dbm(self):
        # busy wait for the other consumers to be done with this
        while True:
            try:
                return dbm.open(str(self.path), 'w')
            except dbm.error:
                sleep(0.05)

    def __getitem__(self, key):
        with self._dbm as d:
            return d[key]

    def __setitem__(self, key, value):
        with self._dbm as d:
            d[key] = value

    def __delitem__(self, key):
        with self._dbm as d:
            del d[key]

    def pop(self, key):
        with self._dbm as d:
            value = d[key]
            del d[key]
            return value

    def keys(self):
        with self._dbm as d:
            return d.keys()


if sys.platform.startswith('win'):
    def sanitize_filename(name):
        for invalid_character in r':*?"\/|<>[]':
            name.replace(invalid_character, '')
        return name
else:
    def sanitize_filename(name):
        return name.replace('/', '')

sanitize_filename.__doc__ = """\
Sanitize a filename so that it is safe to write to the filesystem.

Parameters
----------
name : str
    The name of the file without the directory.

Returns
-------
sanitized_name : str
    The name with invalid characters stripped out.
"""


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
                 download_url=DEFAULT_DOWNLOAD_URL,
                 _overwrite=False):
        self.path = path = pathlib.Path(path)

        self._read_beatmap = lru_cache(cache)(self._raw_read_beatmap)
        self._cache = Cache(path / '.slider.db', overwrite=_overwrite)
        self._download_url = download_url

    def close(self):
        """Close any resources used by this library.
        """
        self._read_beatmap.cache_clear()
        self._cache.close()

    def __del__(self):
        try:
            self.close()
        except AttributeError:
            # if an error is raised in the constructor
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    @staticmethod
    def _osu_files(path, recurse):
        """An iterator of ``.osu`` filepaths in a directory.

        Parameters
        ----------
        path : path-like
            The directory to search in.
        recurse : bool
            Recursively search ``path``?

        Yields
        ------
        path : str
            The path to a ``.osu`` file.
        """
        if recurse:
            for directory, _, filenames in os.walk(path):
                for filename in filenames:
                    if filename.endswith('.osu'):
                        yield os.path.join(directory, filename)
        else:
            for entry in os.scandir(directory):
                path = entry.path
                if path.endswith('.osu'):
                    yield path

    @classmethod
    def create_db(cls,
                  path,
                  *,
                  recurse=True,
                  cache=DEFAULT_CACHE_SIZE,
                  download_url=DEFAULT_DOWNLOAD_URL,
                  show_progress=False):
        """Create a Library from a directory of ``.osu`` files.

        Parameters
        ----------
        path : path-like
            The path to the directory to read.
        recurse : bool, optional
            Recursively search for beatmaps?
        cache : int, optional
            The amount of beatmaps to cache in memory. This uses
            :func:`functools.lru_cache`, and if set to None will cache
            everything.
        download_url : str, optional
            The default location to download beatmaps from.
        show_progress : bool, optional
            Display a progress bar?

        Notes
        -----
        Moving the underlying ``.osu`` files invalidates the library. If this
        happens, just re-run ``create_db`` again.
        """
        self = cls(path, _overwrite=True)
        write_to_cache = self._write_to_cache

        progress = maybe_show_progress(
            self._osu_files(path, recurse=recurse),
            show_progress,
            label='Processing beatmaps: ',
            item_show_func=lambda path: path,
        )
        with progress as it:
            for path in it:
                with open(path, 'rb') as f:
                    data = f.read()

                try:
                    beatmap = Beatmap.parse(data.decode('utf-8-sig'))
                except ValueError as e:
                    raise ValueError(f'failed to parse {path}') from e

                write_to_cache(beatmap, data, path)

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
            if not download:
                raise
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

        path = self.path / sanitize_filename(
            f'{beatmap.artist} - '
            f'{beatmap.title} '
            f'({beatmap.creator})'
            f'[{beatmap.version}]'
            f'.osu'
        )
        with open(path, 'wb') as f:
            f.write(data)

        self._write_to_cache(beatmap, data, path)
        return beatmap

    def delete(self, beatmap, *, remove_file=True):
        """Remove a beatmap from the library.

        Parameters
        ----------
        beatmap : Beatmap
            The beatmap to delete.
        remove_file : bool, optional
            Remove the .osu file from disk.
        """
        path = self._cache.pop(f'id:{beatmap.beatmap_id}')
        md5 = self._cache.pop(f'id_to_md5:{beatmap.beatmap_id}')
        del self._cache[f'md5:{md5}']
        if remove_file:
            os.unlink(path)

    def _write_to_cache(self, beatmap, data, path):
        """Write data to the cache.

        Parameters
        ----------
        beatmap : Beatmap
            The beatmap being stored.
        data : bytes
            The raw data for the beatmap
        path : str
            The path to save
        """
        path = os.path.abspath(path)

        beatmap_md5 = md5(data).hexdigest()
        self._cache[f'md5:{beatmap_md5}'] = path

        beatmap_id = beatmap.beatmap_id
        if beatmap_id is not None:
            # very old beatmaps didn't store the id in the ``.osu``
            # file
            self._cache[f'id:{beatmap_id}'] = path
            # map the id back to the hash
            self._cache[f'id_to_md5:{{beatmap_id}}'] = beatmap_md5

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

    @property
    def md5s(self):
        return tuple(
            key[4:] for key in self._cache.keys() if key.startswith(b'md5:')
        )

    @property
    def ids(self):
        return tuple(
            int(key[3:])
            for key in self._cache.keys()
            if key.startswith(b'id:')
        )
