Replays
=======

Osu! saves player replays in the osu!/data/r directory as ``.osr`` files. We can use
slider to read and process these binary files. Slider represents an osu! replay
with the :class:`~slider.replay.Replay` object. This object stores metadata
about the play like the user who was playing, when the replay was recorded, and
the hit counts. The replay also stores a time-series of all of the events the
user performed during the session.

Reading a :class:`~slider.replay.Replay`
----------------------------------------

To read a replay, we first need to get a :class:`~slider.library.Library`. It
might seem odd that we need to know about all of our beatmaps to read a single
replay; however, the replay only stores an md5 hash of the beatmap played, not
the beatmap id. This is likely so that revisions to the map will invalidate the
old replay. The library contains a lookup table from md5 to beatmap object which
is used to resolve the actual :class:`~slider.beatmap.Beatmap` object for the
replay. To parse a replay, we can use :meth:`~slider.replay.Replay.from_path`
and pass the path to the ``.osr`` file along with the
:class:`~slider.library.Library`.

Replay Data
-----------

The replay stores the user's hit counts (``count_300``, ``count_100``,
``count_50``, and ``count_miss``) along with the max combo. The replay also
tells us which mods were used when playing the song. The replay also stores all
of the user input as a time-series of (cursor location, keyboard state)
pairs.

Slider stores this information in a :class:`slider.replay.Action`. The offset
here is an offset from the previous action, not an absolute offset.
