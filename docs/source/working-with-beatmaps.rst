Working with :class:`~slider.beatmap.Beatmap`\s
===============================================

Instantiating a :class:`~slider.beatmap.Beatmap`
------------------------------------------------

A :class:`~slider.beatmap.Beatmap` object can be created directly from a
``.osu`` file with :meth:`~slider.beatmap.Beatmap.from_path`. This function
takes the path to the ``.osu`` file and returns the slider representation of it.

To read an entire beatmap set (``.osz``), there is
:meth:`~slider.beatmap.Beatmap.from_osz_path` which takes the path to the
``.osz`` file and returns a dictionary from version name to
:class:`~slider.beatmap.Beatmap` object.

Managing :class:`~slider.beatmap.Beatmap`\s with a :class:`~slider.library.Library`
-----------------------------------------------------------------------------------

A :class:`~slider.library.Library` is a collection of
:class:`~slider.beatmap.Beatmap` objects which can be looked up by beatmap id
or md5 hash.

Creating a :class:`~slider.library.Library`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CLI
```

Slider libraries can be created from the command line like:

.. code-block:: bash

   $ python -m slider library /path/to/beatmap/root [--recurse/--no-recurse]

.. note::

   To use the CLI, you must install additional dependencies. Use ``pip install
   slider[cli]`` to do so.


This command will search through ``/path/to/beatmap/root`` recursively and store
metadata to allow slider to quickly find the ``.osu`` files. In the root of the
directory a ``.slider.db`` file will be added which holds the lookup tables
needed to fetch the ``.osu`` files on demand. To disable recursive traversal,
you may use ``--no-recurse``.

Programmatic
````````````

A :class:`~slider.library.Library` can be created with
:meth:`~slider.library.Library.create_db` which takes a directory and
recursively searches for ``.osu`` files to add. In the root of the directory a
``.slider.db`` file will be added which holds the lookup tables needed to fetch
the ``.osu`` files on demand.

Downloading New Beatmaps
------------------------

A :class:`~slider.library.Library` also has a
:meth:`~slider.library.Library.download` method for fetching new beatmaps from
the osu! server. This allows us to quickly get any map we need. The fetched map
can optionally be saved to disk with ``save=True`` so that next time the map is
requested we can load it from disk instead of making a web connection.

The :meth:`~slider.library.Library.lookup_by_id` method also accepts a
``download=True`` argument which will fallback to downloading the map from the
osu! server if it is not in the local library.

Removing a Beatmap
------------------

:meth:`~slider.library.Library.delete` will remove a
:class:`~slider.beatmap.Beatmap` from the library. ``remove_file=False`` may be
passed to preserve the underlying ``.osu`` file while removing the metadata from
the internal library database.
