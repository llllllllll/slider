Model
=====

Slider includes a model for predicting a player's accuracy on a new beatmap
based on their replay data. This is currently an optional dependency which can
be installed with ``pip install slider[model]``.

The slider model currently reduces :class:`~slider.beatmap.Beatmap`\s into 31
features. These features can extracted from a :class:`~slider.beatmap.Beatmap`
with :func:`~slider.model.features.extract_features`.

Basic Attributes
----------------

The first set of features are the basic attributes of the map's basic attributes
that you would see in the osu! client. These include:

- circle size (``CS``)
- overall difficulty (``OD``)
- approach rate (``AR``)

Rationale
~~~~~~~~~

These metrics affect how hard it is to make jumps, read the map, or accurately
hit elements. Health drain (``HP``) is not included because it does not affect
accuracy.

Mods
----

The model accounts for some mods that affect the difficulty of a song. The mods
included are:

- easy (``EZ``)
- hidden (``HD``)
- hard rock (``HR``)
- double time (``DT``) (or nightcore ``NC``)
- half time (``HT``)
- flashlight (``FL``)

.. note::

   If a mod is enabled that affects the basic attributes, those will be adjusted
   to account for this information. If a mod is enabled that affects the BPM,
   the ``bpm_min`` and ``bpm_max`` will be adjusted.

   The ``OD`` and ``AR`` are adjusted when using ``DT`` or ``HT`` to help the
   model make better predictions.

Rationale
~~~~~~~~~

These mods change the ability to read the map or play accurately.

BPM
---

The model accounts for the bpm with two values: ``bpm-min`` and
``bpm-max``. Songs with tempo changes will have different values here.

Rationale
~~~~~~~~~

The BPM affects how hard it is to accurately hit streams or single tap.

Hit Objects
-----------

The model has ``circle-count``, ``slider-count``, and ``spinner-count`` to count
the given element kinds.

Rationale
~~~~~~~~~

The number of each kind of hit element in combination with other metrics can
give a sense of the "kind" of map. For example, a high bpm song with many
circles and few sliders is probably very stream heavy.

Note Angles
-----------

Imagine an osu! standard beatmap in 3d space as ``(x, y, time)``, where the hit
elements form a path through this space. We can look at the angle from hit
object to hit object about each axis to get a sense of how "far" a jump is.

The model looks at the median, mean, and max angle magnitude about each axis.

Rationale
~~~~~~~~~

More extreme jumps are harder to hit and make maps harder to read. Maps with
small angles are likely stream maps where the element to element distance is
very small.

We look at median to get a sense of how much of a jump is any given note.

The max is to look at the most extreme jump in the map. Many maps have one or
two very hard jumps that cause misses. The hardest jump should account for that.

The mean shows how hard the jumps are across all of the notes. Comparing this to
median can give us a sense of how much more extreme the outliers are.

Osu! Difficulty Metrics
-----------------------

Osu! itself has a couple of metrics for measuring difficulty, these include:

- speed stars: a measure of how hard a song is from speed
- aim stars: a measure of how hard a song is to aim and accurately hit each
  object.
- rhythm awkwardness: how difficult is the rhythm of the beatmap

.. note::

   The speed and aim stars add up to the final value shown in the osu! client.

Rationale
~~~~~~~~~

The osu! team put a lot of work into these criteria, they are what I as a player
mainly use to know how hard a song is.

Performance Points Curve
------------------------

The model takes into account the performance points awarded for 95%-100%
accuracies at 1% steps.

Rationale
~~~~~~~~~

Like the raw difficulty metrics, the osu! team put a lot of work into defining
the performance points algorithm and I believe there is predictive power in it.
