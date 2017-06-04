What is a Beatmap?
==================

A Beatmap in osu! is a description of song, including metadata like title and
artist as well as the locations of all of the circles, sliders, and
spinners. Osu! stores this information in ``.osu`` files. The ``.osu`` format is
a text format like an ``.ini`` file with extensions for encoding the
time-series of hit objects.

In slider, the :class:`~slider.beatmap.Beatmap` object represents a beatmap and
exposes the information from the ``.osu`` file.

Hit Objects
-----------

A hit object is the generic term for a circle, slider, or spinner. These are the
things you click in osu!. A hit object is composed of the (x, y, time) position
in the map and the type. For some types of objects, there is some extra
information.

The (x, y) bounds for all hit objects are [0, 512] by [0, 384]. All hit objects
fall within these bounds regardless of your resolution or window size.

Sliders
```````

For sliders, the (x, y, time) coordinate is for the start of the slider. The
curve is encoded as a curve type, one of Linear, Bezier, Perfect, or Catmull,
and the control points. The control points are a sequence of (x, y) coordinates
which are interpreted by the curve type to define the shape of the
slider. Control points may fall outside of the [0, 512] by [0, 384] bounds
because they don't actually appear on your screen explicitly.

Spinners
````````

In addition to (x, y, time), spinners must encode the duration.
