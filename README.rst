slider
======

Utilities for working with `osu! <https://osu.ppy.sh/>`_ files and data.

`Read the docs! <https://llllllllll.github.io/slider>`_

Included Tools
--------------

Beatmap Parser
~~~~~~~~~~~~~~

Slider includes an osu! beatmap parser for programatic access and manipulation of
``.osu`` and ``.osz`` files.

Replay Parser
~~~~~~~~~~~~~

Slider includes an osu! replay parser for reading metadata, 300/100/50/miss
counts, and input stream data out of ``.osr`` files.

Osu! API
~~~~~~~~

Slider includes a Python interface to the osu! web API for requesting
information about users or beatmaps.

Dependencies
------------

Slider currently requires Python 3.6+.

Slider also requires a few PyData tools like numpy and scipy; see the
``setup.py`` for a full list of required packages.

Thanks
------

I would like to thank `peppy <https://github.com/peppy>`_ for creating osu! and
providing resources for writing these tools.
