Osu! API
========

Peppy, being the hero that he is, exposes a web API for making queries about
osu!. Slider provides a Python interface to this web API through a
:class:`~slider.client.Client` object. The client knows how to format messages
to send to the osu! API and knows how to parse the results returned. It will
also attempt to do argument validation client side to avoid making a bad web
request.

User Information
----------------

The :class:`~slider.client.Client` can fetch user information with the
:meth:`~slider.client.Client.user` method. This method can look up a user by
either username or user id. It will explicitly tell the osu! server which
identifier you are using to avoid ambiguity. The method also accepts the game
mode to fetch information about.

High Scores
~~~~~~~~~~~

If we already have a :class:`~slider.client.User` object, we can request their
high scores with the :meth:`~slider.client.User.high_scores` method. This will
return a list of :class:`~slider.client.HighScore` objects which has metadata
about the play like which map it was and the hit counts. Right now there is no
way to recover the :class:`~slider.replay.Replay` object from the
:class:`~slider.client.HighScore`.

If we do not yet have a :class:`~slider.client.User` object, we can request the
high scores directly with :meth:`~slider.client.Client.user_best`. This takes
the user identifier and game mode but just directly returns the list of
:class:`~slider.client.HighScore` objects. This method is more efficient if you
only want to get the high scores for a user.

Beatmaps
--------

The osu! API allows us to query for beatmaps themselves. Slider exposes this
through the :meth:`~slider.client.Client.beatmap` method. This method can either
be used to look up a single beatmap by id or md5 hash, or to fetch maps in bulk
by date ranked.

.. note::

   When fetching maps in bulk, we can only get 500 results at a time.

When we get results from the :meth:`~slider.client.Client.beatmap` method, they
are returned as :class:`~slider.client.BeatmapResult` objects instead of the
normal :class:`slider.beatmap.Beatmap`. The
:class:`~slider.client.BeatmapResult` object holds the extra information about a
map which is only available through the client, for example: the pass and play
counts.

The :class:`~slider.client.Beatmap` can be fetched from the
:class:`~slider.client.BeatmapResult` object with the
:meth:`~slider.client.BeatmapResult.beatmap` method. This can be passed
``save=True`` to save the downloaded ``.osu`` file into the
:class:`~slider.library.Library`.
