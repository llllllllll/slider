from datetime import timedelta
from enum import unique, IntEnum
from functools import partial
import inspect
from itertools import chain, islice, cycle
import operator as op
import re
from zipfile import ZipFile

import numpy as np

from .game_mode import GameMode
from .mod import ar_to_ms, ms_to_ar, circle_radius, od_to_ms_300, ms_300_to_od
from .position import Position, Point
from .utils import (
    accuracy as calculate_accuracy,
    lazyval,
    memoize,
    no_default,
    orange,
)
from .curve import Curve


def _get(cs, ix, default=no_default):
    try:
        return cs[ix]
    except IndexError:
        if default is no_default:
            raise
        return default


class TimingPoint:
    """A timing point assigns properties to an offset into a beatmap.

    Parameters
    ----------
    offset : timedelta
        When this ``TimingPoint`` takes effect.
    ms_per_beat : float
        The milliseconds per beat, this is another representation of BPM.
    meter : int
        The number of beats per measure.
    sample_type : int
        The type of hit sound samples that are used.
    sample_set : int
        The set of hit sound samples that are used.
    volume : int
        The volume of hit sounds in the range [0, 100]. This value will be
        clipped if outside the range.
    parent : TimingPoint or None
        The parent of an inherited timing point. An inherited timing point
        differs from a normal timing point in that the ``ms_per_beat`` value is
        negative, and defines a new ``ms_per_beat`` based on the parent
        timing point. This can be used to change volume without affecting
        offset timing, or changing slider speeds. If this is not an inherited
        timing point the parent should be ``None``.
    kiai_mode : bool
        Wheter or not kiai time effects are active.
    """
    def __init__(self,
                 offset,
                 ms_per_beat,
                 meter,
                 sample_type,
                 sample_set,
                 volume,
                 parent,
                 kiai_mode):
        self.offset = offset
        self.ms_per_beat = ms_per_beat
        self.meter = meter
        self.sample_type = sample_type
        self.sample_set = sample_set
        self.volume = np.clip(volume, 0, 100)
        self.parent = parent
        self.kiai_mode = kiai_mode

    @lazyval
    def half_time(self):
        """The ``TimingPoint`` as it would appear with
        :data:`~slider.mod.Mod.half_time` enabled.
        """
        return type(self)(
            4 * self.offset / 3,
            self.ms_per_beat if self.inherited else (4 * self.ms_per_beat / 3),
            self.meter,
            self.sample_type,
            self.sample_set,
            self.volume,
            getattr(self.parent, 'half_time', None),
            self.kiai_mode,
        )

    def double_time(self):
        """The ``TimingPoint`` as it would appear with
        :data:`~slider.mod.Mod.double_time` enabled.
        """
        return type(self)(
            2 * self.offset / 3,
            self.ms_per_beat if self.inherited else (2 * self.ms_per_beat / 3),
            self.meter,
            self.sample_type,
            self.sample_set,
            self.volume,
            getattr(self.parent, 'double_time', None),
            self.kiai_mode,
        )

    @lazyval
    def bpm(self):
        """The bpm of this timing point.

        If this is an inherited timing point this value will be None.
        """
        ms_per_beat = self.ms_per_beat
        if ms_per_beat < 0:
            return None
        return round(60000 / ms_per_beat)

    def __repr__(self):
        if self.parent is None:
            inherited = 'inherited '
        else:
            inherited = ''
        return (
            f'<{type(self).__qualname__}:'
            f' {inherited}{self.offset.total_seconds() * 1000:g}ms>'
        )

    @classmethod
    def parse(cls, data, parent):
        """Parse a TimingPoint object from a line in a ``.osu`` file.

        Parameters
        ----------
        data : str
            The line to parse.
        parent : TimingPoint
            The last non-inherited timing point.

        Returns
        -------
        timing_point : TimingPoint
            The parsed timing point.

        Raises
        ------
        ValueError
            Raised when ``data`` does not describe a ``TimingPoint`` object.
        """
        try:
            offset, ms_per_beat, *rest = data.split(',')
        except ValueError:
            raise ValueError(
                f'failed to parse {cls.__qualname__} from {data!r}',
            )

        try:
            offset_float = float(offset)
        except ValueError:
            raise ValueError(f'offset should be a float, got {offset!r}')

        offset = timedelta(milliseconds=offset_float)

        try:
            ms_per_beat = float(ms_per_beat)
        except ValueError:
            raise ValueError(
                f'ms_per_beat should be a float, got {ms_per_beat!r}',
            )

        try:
            meter = int(_get(rest, 0, '4'))
        except ValueError:
            raise ValueError(f'meter should be an int, got {meter!r}')

        try:
            sample_type = int(_get(rest, 1, '0'))
        except ValueError:
            raise ValueError(
                f'sample_type should be an int, got {sample_type!r}',
            )

        try:
            sample_set = int(_get(rest, 2, '0'))
        except ValueError:
            raise ValueError(
                f'sample_set should be an int, got {sample_set!r}',
            )

        try:
            volume = int(_get(rest, 3, '1'))
        except ValueError:
            raise ValueError(f'volume should be an int, got {volume!r}')

        try:
            inherited = not bool(int(_get(rest, 4, '1')))
        except ValueError:
            raise ValueError(f'inherited should be a bool, got {inherited!r}')

        try:
            kiai_mode = bool(int(_get(rest, 5, '0')))
        except ValueError:
            raise ValueError(f'kiai_mode should be a bool, got {kiai_mode!r}')

        return cls(
            offset=offset,
            ms_per_beat=ms_per_beat,
            meter=meter,
            sample_type=sample_type,
            sample_set=sample_set,
            volume=volume,
            parent=parent if inherited else None,
            kiai_mode=kiai_mode,
        )


class HitObject:
    """An abstract hit element for osu! standard.

    Parameters
    ----------
    position : Position
        Where this element appears on the screen.
    time : timedelta
        When this element appears in the map.
    hitsound : int
        The hitsound to play when this object is hit.
    addition : str, optional
        Unknown currently.
    """
    time_related_attributes = frozenset({'time'})

    def __init__(self, position, time, hitsound, addition='0:0:0:0'):
        self.position = position
        self.time = time
        self.hitsound = hitsound
        self.addition = addition

    def __repr__(self):
        return (
            f'<{type(self).__qualname__}: {self.position},'
            f' {self.time.total_seconds() * 1000:g}ms>'
        )

    def _time_modify(self, coefficient):
        """Modify this ``HitObject`` by multiplying time related attributes
        by the ``coefficient``.

        Parameters
        ----------
        coefficient : float
            The coefficient to multiply the ``time_related`` values by.

        Returns
        -------
        modified : HitObject
            The modified hit object.
        """
        time_related_attributes = self.time_related_attributes
        kwargs = {}
        for name in inspect.signature(type(self)).parameters:
            value = getattr(self, name)
            if name in time_related_attributes:
                value *= coefficient
            kwargs[name] = value

        return type(self)(**kwargs)

    @lazyval
    def half_time(self):
        """The ``HitObject`` as it would appear with
        :data:`~slider.mod.Mod.half_time` enabled.
        """
        return self._time_modify(4 / 3)

    @lazyval
    def double_time(self):
        """The ``HitObject`` as it would appear with
        :data:`~slider.mod.Mod.double_time` enabled.
        """
        return self._time_modify(2 / 3)

    @lazyval
    def hard_rock(self):
        """The ``HitObject`` as it would appear with
        :data:`~slider.mod.Mod.hard_rock` enabled.
        """
        kwargs = {}
        for name in inspect.signature(type(self)).parameters:
            value = getattr(self, name)
            if name == 'position':
                value = Position(value.x, 384 - value.y)
            kwargs[name] = value

        return type(self)(**kwargs)

    @classmethod
    def parse(cls, data, timing_points, slider_multiplier, slider_tick_rate):
        """Parse a HitObject object from a line in a ``.osu`` file.

        Parameters
        ----------
        data : str
            The line to parse.
        timing_points : list[TimingPoint]
            The timing points in the map.
        slider_multiplier : float
            The slider multiplier for computing slider end_time and ticks.
        slider_tick_rate : float
            The slider tick rate for computing slider end_time and ticks.

        Returns
        -------
        hit_objects : HitObject
            The parsed hit object. This will be the concrete subclass given
            the type.

        Raises
        ------
        ValueError
            Raised when ``data`` does not describe a ``HitObject`` object.
        """
        try:
            x, y, time, type_, hitsound, *rest = data.split(',')
        except ValueError:
            raise ValueError(f'not enough elements in line, got {data!r}')

        try:
            x = int(x)
        except ValueError:
            raise ValueError(f'x should be an int, got {x!r}')

        try:
            y = int(y)
        except ValueError:
            raise ValueError(f'y should be an int, got {y!r}')

        try:
            time = timedelta(milliseconds=int(time))
        except ValueError:
            raise ValueError(f'type should be an int, got {time!r}')

        try:
            type_ = int(type_)
        except ValueError:
            raise ValueError(f'type should be an int, got {type_!r}')

        try:
            hitsound = int(hitsound)
        except ValueError:
            raise ValueError(f'hitsound should be an int, got {hitsound!r}')

        if type_ & Circle.type_code:
            parse = Circle._parse
        elif type_ & Slider.type_code:
            parse = partial(
                Slider._parse,
                timing_points=timing_points,
                slider_multiplier=slider_multiplier,
                slider_tick_rate=slider_tick_rate,
            )
        elif type_ & Spinner.type_code:
            parse = Spinner._parse
        elif type_ & HoldNote.type_code:
            parse = HoldNote._parse
        else:
            raise ValueError(f'unknown type code {type_!r}')

        return parse(Position(x, y), time, hitsound, rest)


class Circle(HitObject):
    """A circle hit element.

    Parameters
    ----------
    position : Position
        Where this circle appears on the screen.
    time : timedelta
        When this circle appears in the map.
    """
    type_code = 1

    @classmethod
    def _parse(cls, position, time, hitsound, rest):
        if len(rest) > 1:
            raise ValueError('extra data: {rest!r}')

        return cls(position, time, hitsound, *rest)


class Spinner(HitObject):
    """A spinner hit element

    Parameters
    ----------
    position : Position
        Where this spinner appears on the screen.
    time : timedelta
        When this spinner appears in the map.
    end_time : timedelta
        When this spinner ends in the map.
    addition : str
        Hitsound additions.
    """
    type_code = 8
    time_related_attributes = frozenset({'time', 'end_time'})

    def __init__(self,
                 position,
                 time,
                 hitsound,
                 end_time,
                 addition='0:0:0:0:'):
        super().__init__(position, time, hitsound, addition)
        self.end_time = end_time

    @classmethod
    def _parse(cls, position, time, hitsound, rest):
        try:
            end_time, *rest = rest
        except ValueError:
            raise ValueError('missing end_time')

        try:
            end_time = timedelta(milliseconds=int(end_time))
        except ValueError:
            raise ValueError(f'end_time should be an int, got {end_time!r}')

        if len(rest) > 1:
            raise ValueError(f'extra data: {rest!r}')

        return cls(position, time, hitsound, end_time, *rest)


class Slider(HitObject):
    """A slider hit element.

    Parameters
    ----------
    position : Position
        Where this slider appears on the screen.
    time : datetime.timedelta
        When this slider appears in the map.
    end_time : datetime.timedelta
        When this slider ends in the map
    hitsound : int
        The sound played on the ticks of the slider.
    curve : Curve
        The slider's curve function.
    length : int
        The length of this slider in osu! pixels.
    ticks : int
        The number of slider ticks including the head and tail of the slider.
    num_beats : int
        The number of beats that this slider spans.
    tick_rate : float
        The rate at which ticks appear along sliders.
    ms_per_beat : int
        The milliseconds per beat during the segment of the beatmap that this
        slider appears in.
    edge_sounds : list[int]
        A list of hitsounds for each edge.
    edge_additions : list[str]
        A list of additions for each edge.
    addition : str
        Hitsound additions.
    """
    type_code = 2
    time_related_attributes = frozenset({'time', 'end_time', 'ms_per_beat'})

    def __init__(self,
                 position,
                 time,
                 end_time,
                 hitsound,
                 curve,
                 repeat,
                 length,
                 ticks,
                 num_beats,
                 tick_rate,
                 ms_per_beat,
                 edge_sounds,
                 edge_additions,
                 addition='0:0:0:0'):
        super().__init__(position, time, hitsound, addition)
        self.end_time = end_time
        self.curve = curve
        self.repeat = repeat
        self.length = length
        self.ticks = ticks
        self.num_beats = num_beats
        self.tick_rate = tick_rate
        self.ms_per_beat = ms_per_beat
        self.edge_sounds = edge_sounds
        self.edge_additions = edge_additions

    @lazyval
    def tick_points(self):
        """The position and time of each slider tick.
        """
        repeat = self.repeat

        time = self.time
        repeat_duration = (self.end_time - time) / repeat

        curve = self.curve

        pre_repeat_ticks = []
        append_tick = pre_repeat_ticks.append

        beats_per_repeat = self.num_beats / repeat
        for t in orange(self.tick_rate, beats_per_repeat, self.tick_rate):
            pos = curve(t / beats_per_repeat)
            timediff = timedelta(milliseconds=t * self.ms_per_beat)
            append_tick(Point(pos.x, pos.y, time + timediff))

        pos = curve(1)
        timediff = repeat_duration
        append_tick(Point(pos.x, pos.y, time + timediff))

        repeat_ticks = [
            Point(p.x, p.y, pre_repeat_tick.offset)
            for pre_repeat_tick, p in zip(
                pre_repeat_ticks,
                chain(pre_repeat_ticks[-2::-1], [self.position])
            )
        ]

        tick_sequences = islice(
            cycle([pre_repeat_ticks, repeat_ticks]),
            repeat,
        )
        return list(
            chain.from_iterable(
                (
                    Point(p.x, p.y, p.offset + n * repeat_duration)
                    for p in tick_sequence
                )
                for n, tick_sequence in enumerate(tick_sequences)
            ),
        )

    @lazyval
    def hard_rock(self):
        """The ``HitObject`` as it would appear with
        :data:`~slider.mod.Mod.hard_rock` enabled.
        """
        kwargs = {}
        for name in inspect.signature(type(self)).parameters:
            value = getattr(self, name)
            if name == 'position':
                value = Position(value.x, 384 - value.y)
            elif name == 'curve':
                value = value.hard_rock
            kwargs[name] = value

        return type(self)(**kwargs)

    @classmethod
    def _parse(cls,
               position,
               time,
               hitsound,
               rest,
               timing_points,
               slider_multiplier,
               slider_tick_rate):
        try:
            group_1, *rest = rest
        except ValueError:
            raise ValueError(f'missing required slider data in {rest!r}')

        try:
            slider_type, *raw_points = group_1.split('|')
        except ValueError:
            raise ValueError(
                'expected slider type and points in the first'
                f' element of rest, {rest!r}',
            )

        points = [position]
        for point in raw_points:
            try:
                x, y = point.split(':')
            except ValueError:
                raise ValueError(
                    f'expected points in the form x:y, got {point!r}',
                )

            try:
                x = int(x)
            except ValueError:
                raise ValueError('x should be an int, got {x!r}')

            try:
                y = int(y)
            except ValueError:
                raise ValueError('y should be an int, got {y!r}')

            points.append(Position(x, y))

        try:
            repeat, *rest = rest
        except ValueError:
            raise ValueError(f'missing repeat in {rest!r}')

        try:
            repeat = int(repeat)
        except ValueError:
            raise ValueError(f'repeat should be an int, got {repeat!r}')

        try:
            pixel_length, *rest = rest
        except ValueError:
            raise ValueError(f'missing pixel_length in {rest!r}')

        try:
            pixel_length = float(pixel_length)
        except ValueError:
            raise ValueError(
                f'pixel_length should be a float, got {pixel_length!r}',
            )

        try:
            raw_edge_sounds_grouped, *rest = rest
        except ValueError:
            raw_edge_sounds_grouped = ''

        raw_edge_sounds = raw_edge_sounds_grouped.split('|')
        edge_sounds = []
        if raw_edge_sounds != ['']:
            for edge_sound in raw_edge_sounds:
                try:
                    edge_sound = int(edge_sound)
                except ValueError:
                    raise ValueError(
                        f'edge_sound should be an int, got {edge_sound!r}',
                    )
                edge_sounds.append(edge_sound)

        try:
            edge_additions_grouped, *rest = rest
        except ValueError:
            edge_additions_grouped = ''

        if edge_additions_grouped:
            edge_additions = edge_additions_grouped.split('|')
        else:
            edge_additions = []

        if len(rest) > 1:
            raise ValueError(f'extra data: {rest!r}')

        for tp in reversed(timing_points):
            if tp.offset <= time:
                break
        else:
            tp = timing_points[0]

        if tp.parent is not None:
            velocity_multiplier = -100 / tp.ms_per_beat
            ms_per_beat = tp.parent.ms_per_beat
        else:
            velocity_multiplier = 1
            ms_per_beat = tp.ms_per_beat

        pixels_per_beat = slider_multiplier * 100 * velocity_multiplier
        num_beats = (
            np.round(((pixel_length * repeat) / pixels_per_beat) * 16) / 16
        )
        duration = timedelta(milliseconds=np.ceil(num_beats * ms_per_beat))

        ticks = int(
            (
                (np.ceil((num_beats - 0.1) / repeat * slider_tick_rate) - 1)
            ) *
            repeat +
            repeat +
            1
        )

        return cls(
            position,
            time,
            time + duration,
            hitsound,
            Curve.from_kind_and_points(slider_type, points, pixel_length),
            repeat,
            pixel_length,
            ticks,
            num_beats,
            slider_tick_rate,
            ms_per_beat,
            edge_sounds,
            edge_additions,
            *rest,
        )


class HoldNote(HitObject):
    """A HoldNote hit element.

    Parameters
    ----------
    position : Position
        Where this HoldNote appears on the screen.
    time : timedelta
        When this HoldNote appears in the map.

    Notes
    -----
    A ``HoldNote`` can only appear in an osu!mania map.
    """
    type_code = 128

    @classmethod
    def _parse(cls, position, time, hitsound, rest):
        if len(rest) > 1:
            raise ValueError('extra data: {rest!r}')

        return cls(position, time, hitsound, *rest)


def _get_as_str(groups, section, field, default=no_default):
    """Lookup a field from a given section.

    Parameters
    ----------
    groups : dict[str, dict[str, str]]
        The grouped osu! file.
    section : str
        The section to read from.
    field : str
        The field to read.
    default : int, optional
        A value to return if ``field`` is not in ``groups[section]``.

    Returns
    -------
    cs : str
        ``groups[section][field]`` or default if ``field` is not in
         ``groups[section]``.
    """
    try:
        mapping = groups[section]
    except KeyError:
        if default is no_default:
            raise ValueError(f'missing section {section!r}')
        return default

    try:
        return mapping[field]
    except KeyError:
        if default is no_default:
            raise ValueError(f'missing field {field!r} in section {section!r}')
        return default


def _get_as_int(groups, section, field, default=no_default):
    """Lookup a field from a given section and parse it as an integer.

    Parameters
    ----------
    groups : dict[str, dict[str, str]]
        The grouped osu! file.
    section : str
        The section to read from.
    field : str
        The field to read and parse.
    default : int, optional
        A value to return if ``field`` is not in ``groups[section]``.

    Returns
    -------
    integer : int
        ``int(groups[section][field])`` or default if ``field` is not in
        ``groups[section]``.
    """
    v = _get_as_str(groups, section, field, default)

    if v is default:
        return v

    try:
        return int(v)
    except ValueError:
        raise ValueError(
            f'field {field!r} in section {section!r} should be an int,'
            f' got {v!r}',
        )


def _get_as_int_list(groups, section, field, default=no_default):
    """Lookup a field from a given section and parse it as an integer list.

    Parameters
    ----------
    groups : dict[str, dict[str, str]]
        The grouped osu! file.
    section : str
        The section to read from.
    field : str
        The field to read and parse.
    default : int, optional
        A value to return if ``field`` is not in ``groups[section]``.

    Returns
    -------
    ints : list[int]
        ``int(groups[section][field])`` or default if ``field` is not in
        ``groups[section]``.
    """
    v = _get_as_str(groups, section, field, default)

    if v is default:
        return v

    try:
        return [int(e.strip()) for e in v.split(',')]
    except ValueError:
        raise ValueError(
            f'field {field!r} in section {section!r} should be an int list,'
            f' got {v!r}',
        )


def _get_as_float(groups, section, field, default=no_default):
    """Lookup a field from a given section and parse it as an float

    Parameters
    ----------
    groups : dict[str, dict[str, str]]
        The grouped osu! file.
    section : str
        The section to read from.
    field : str
        The field to read and parse.
    default : float, optional
        A value to return if ``field`` is not in ``groups[section]``.

    Returns
    -------
    f : float
        ``float(groups[section][field])`` or default if ``field` is not in
        ``groups[section]``.
    """
    v = _get_as_str(groups, section, field, default)

    if v is default:
        return v

    try:
        return float(v)
    except ValueError:
        raise ValueError(
            f'field {field!r} in section {section!r} should be a float,'
            f' got {v!r}',
        )


def _get_as_bool(groups, section, field, default=no_default):
    """Lookup a field from a given section and parse it as an float

    Parameters
    ----------
    groups : dict[str, dict[str, str]]
        The grouped osu! file.
    section : str
        The section to read from.
    field : str
        The field to read and parse.
    default : float, optional
        A value to return if ``field`` is not in ``groups[section]``.

    Returns
    -------
    f : float
        ``float(groups[section][field])`` or default if ``field` is not in
        ``groups[section]``.
    """
    v = _get_as_str(groups, section, field, default)

    if v is default:
        return v

    try:
        # cast to int then to bool because '0' is still True; bools are written
        # to the file as '0' and '1' so this is safe.
        return bool(int(v))
    except ValueError:
        raise ValueError(
            f'field {field!r} in section {section!r} should be a bool,'
            f' got {v!r}',
        )


def _moving_average_by_time(times, data, delta, num):
    """Take the moving average of some values and sample it at regular
    frequencies.

    Parameters
    ----------
    times : np.ndarray
        The array of times to use in the average.
    data : np.ndarray
        The array of values to take the average of. Each column is averaged
        independently.
    delta : int or float
        The length of the leading and trailing window in seconds
    num : int
        The number of samples to take.

    Returns
    -------
    times : np.ndarray
        A column vector of the times sampled at.
    averages : np.ndarray
        A column array of the averages. 1 column per column in the input
    """

    # take an even sample from 0 to the end time
    out_times = np.linspace(
        times[0].item(),
        times[-1].item(),
        num,
        dtype='timedelta64[ns]',
    )
    delta = np.timedelta64(int(delta * 1e9), 'ns')

    # compute the start and stop indices for each sampled window
    window_start_ixs = np.searchsorted(times[:, 0], out_times - delta)
    window_stop_ixs = np.searchsorted(times[:, 0], out_times + delta)

    # a 2d array of shape ``(num, 2)`` where each row holds the start and stop
    # index for the window
    window_ixs = np.stack([window_start_ixs, window_stop_ixs], axis=1)

    # append a nan to the end of the values so that we can do many slices all
    # the way to the end in reduceat
    values = np.vstack([data, [np.nan] * data.shape[1]])

    # sum the values in the ranges ``[window_start_ixs, window_stop_ixs)``
    window_sums = np.add.reduceat(values, window_ixs.ravel())[::2]
    window_sizes = np.diff(window_ixs, axis=1).ravel()
    # convert window_sizes of 0 to 1 (inplace) to prevent division by zero
    np.clip(window_sizes, 1, None, out=window_sizes)

    out_values = np.stack(window_sums / window_sizes.reshape((-1, 1)))

    return out_times.reshape((-1, 1)), out_values


class _DifficultyHitObject:
    """An object used to accumulate the strain information for calculating
    stars.

    Parameters
    ----------
    hit_object : HitObject
        The hit object to wrap.
    radius : int
        The circle radius
    previous : _DifficultyHitObject, optional
        The previous difficulty hit object.
    """
    decay_base = 0.3, 0.15

    almost_diameter = 90

    stream_spacing = 110
    single_spacing = 125

    weight_scaling = 1400, 26.25

    circle_size_buffer_threshold = 30

    @unique
    class Strain(IntEnum):
        """Indices for the strain specific values.
        """
        speed = 0
        aim = 1

    def __init__(self, hit_object, radius, previous=None):
        self.hit_object = hit_object

        scaling_factor = 52 / radius
        if radius < self.circle_size_buffer_threshold:
            scaling_factor *= 1 + min(
                self.circle_size_buffer_threshold - radius,
                5,
            ) / 50

        # this currently ignores slider length
        self.normalized_start = self.normalized_end = Position(
            hit_object.position.x * scaling_factor,
            hit_object.position.y * scaling_factor,
        )

        if previous is None:
            self.strains = 0, 0
        else:
            self.strains = (
                self._calculate_strain(previous, self.Strain.speed),
                self._calculate_strain(previous, self.Strain.aim),
            )

    def _calculate_strain(self, previous, strain):
        result = 0
        scaling = self.weight_scaling[strain]

        hit_object = self.hit_object
        if isinstance(hit_object, (Circle, Slider)):
            result = self._spacing_weight(
                self._distance(previous),
                strain
            ) * scaling

        time_elapsed = (
            self.hit_object.time -
            previous.hit_object.time
        ).total_seconds() * 1000
        result /= max(time_elapsed, 50)
        decay = (
            self.decay_base[strain] **
            (time_elapsed / 1000)
        )
        return previous.strains[strain] * decay + result

    def _distance(self, previous):
        """The magnitude of distance between the current object and the
        previous.

        Parameters
        ----------
        previous : _DifficultyHitObject
            The previous difficulty hit object.

        Returns
        -------
        distance : float
            The absolute difference between the two hit objects.
        """
        start = self.normalized_start
        end = previous.normalized_end
        return np.sqrt((start.x - end.x) ** 2 + (start.y - end.y) ** 2)

    def _spacing_weight(self, distance, strain):
        if strain == self.Strain.speed:
            if distance > self.single_spacing:
                return 2.5
            elif distance > self.stream_spacing:
                return (
                    1.6 +
                    0.9 *
                    (distance - self.stream_spacing) /
                    (self.single_spacing - self.stream_spacing)
                )
            elif distance > self.almost_diameter:
                return (
                    1.2 +
                    0.4 *
                    (distance - self.almost_diameter) /
                    (self.stream_spacing - self.almost_diameter)
                )
            elif distance > self.almost_diameter / 2:
                return (
                    0.95 +
                    0.25 *
                    (distance - self.almost_diameter / 2) /
                    (self.almost_diameter / 2.0)
                )
            return 0.95

        return distance ** 0.99


class Beatmap:
    """A beatmap for osu! standard.

    Parameters
    ----------
    format_version : int
        The version of the beatmap file.
    audio_filename : str
        The location of the audio file relative to the unpacked ``.osz``
        directory.
    audio_lead_in : timedelta
        The amount of time added before the audio file begins playing. Useful
        selection menu.
    preview_time : timedelta
        When the audio file should begin playing when selected in the song for
        audio files that begin immediately.
    countdown : bool
        Should the countdown be displayed before the first hit object.
    sample_set : str
        The set of hit sounds to use through the beatmap.
    stack_leniency : float
        How often closely placed hit objects will be placed together.
    mode : GameMode
        The game mode.
    letterbox_in_breaks : bool
        Should the letterbox appear during breaks.
    widescreen_storyboard : bool
        Should the storyboard be widescreen?
    bookmarks : list[timedelta]
        The time for all of the bookmarks.
    distance_spacing : float
        A multiplier for the 'distance snap' feature.
    beat_divisor : int
        The beat division for placing objects.
    grid_size : int
        The size of the grid for the 'grid snap' feature.
    timeline_zoom : float
        The zoom in the editor timeline.
    title : str
        The title of the song limited to ascii characters.
    title_unicode : str
        The title of the song with unicode support.
    artist : str
        The name of the song artist limited to ascii characters.
    artist_unicode : str
        The name of the song artist with unicode support.
    creator : str
        The username of the mapper.
    version : str
        The name of the beatmap's difficulty.
    source : str
        The origin of the song.
    tags : list[str]
        A collection of words describing the song. This is searchable on the
        osu! website.
    beatmap_id : int or None
        The id of this single beatmap. Old beatmaps did not store this in the
        file.
    beatmap_set_id : int or None
        The id of this beatmap set. Old beatmaps did not store this in the
        file.
    hp_drain_rate : float
        The ``HP`` attribute of the beatmap.
    circle_size, : float
        The ``CS`` attribute of the beatmap.
    overall_difficulty : float
        The ``OD`` attribute of the beatmap.
    approach_rate : float
        The ``AR`` attribute of the beatmap.
    slider_multiplier : float
        The multiplier for slider velocity.
    slider_tick_rate : float
        How often slider ticks appear.
    timing_points : list[TimingPoint]
        The timing points the the map.
    hit_objects : list[HitObject]
        The hit objects in the map.

    Notes
    -----
    This is currently missing the storyboard data.
    """
    _version_regex = re.compile(r'^osu file format v(\d+)$')

    def __init__(self,
                 format_version,
                 audio_filename,
                 audio_lead_in,
                 preview_time,
                 countdown,
                 sample_set,
                 stack_leniency,
                 mode,
                 letterbox_in_breaks,
                 widescreen_storyboard,
                 bookmarks,
                 distance_spacing,
                 beat_divisor,
                 grid_size,
                 timeline_zoom,
                 title,
                 title_unicode,
                 artist,
                 artist_unicode,
                 creator,
                 version,
                 source,
                 tags,
                 beatmap_id,
                 beatmap_set_id,
                 hp_drain_rate,
                 circle_size,
                 overall_difficulty,
                 approach_rate,
                 slider_multiplier,
                 slider_tick_rate,
                 timing_points,
                 hit_objects):
        self.format_version = format_version
        self.audio_filename = audio_filename
        self.audio_lead_in = audio_lead_in
        self.preview_time = preview_time
        self.countdown = countdown
        self.sample_set = sample_set
        self.stack_leniency = stack_leniency
        self.mode = mode
        self.letterbox_in_breaks = letterbox_in_breaks
        self.widescreen_storyboard = widescreen_storyboard
        self.bookmarks = bookmarks
        self.distance_spacing = distance_spacing
        self.beat_divisor = beat_divisor
        self.grid_size = grid_size
        self.timeline_zoom = timeline_zoom
        self.title = title
        self.title_unicode = title_unicode
        self.artist = artist
        self.artist_unicode = artist_unicode
        self.creator = creator
        self.version = version
        self.source = source
        self.tags = tags
        self.beatmap_id = beatmap_id
        self.beatmap_set_id = beatmap_set_id
        self.hp_drain_rate = hp_drain_rate
        self.circle_size = circle_size
        self.overall_difficulty = overall_difficulty
        self.approach_rate = approach_rate
        self.slider_multiplier = slider_multiplier
        self.slider_tick_rate = slider_tick_rate
        self.timing_points = timing_points
        self.hit_objects = hit_objects

        # cache the stars with different mod combinations
        self._stars_cache = {}
        self._aim_stars_cache = {}
        self._speed_stars_cache = {}
        self._rhythm_awkwardness_cache = {}

    @property
    def display_name(self):
        """The name of the map as it appears in game.
        """
        return f'{self.artist} - {self.title} [{self.version}]'

    @memoize
    def bpm_min(self, *, half_time=False, double_time=False):
        """The minimum BPM in this beatmap.

        Parameters
        ----------
        half_time : bool
            The BPM with half time enabled.
        double_time : bool
            The BPM with double time enabled.

        Returns
        -------
        bpm : float
            The minimum BPM in this beatmap.
        """
        bpm = min(p.bpm for p in self.timing_points if p.bpm)
        if double_time:
            bpm *= 1.5
        elif half_time:
            bpm *= 0.75
        return bpm

    @memoize
    def bpm_max(self, *, half_time=False, double_time=False):
        """The maximum BPM in this beatmap.

        Parameters
        ----------
        half_time : bool
            The BPM with half time enabled.
        double_time : bool
            The BPM with double time enabled.

        Returns
        -------
        bpm : float
            The maximum BPM in this beatmap.
        """
        bpm = max(p.bpm for p in self.timing_points if p.bpm)
        if double_time:
            bpm *= 1.5
        elif half_time:
            bpm *= 0.75
        return bpm

    def hp(self, *, easy=False, hard_rock=False):
        """Compute the Health Drain (HP) value for different mods.

        Parameters
        ----------
        easy : bool, optional
            HP with the easy mod enabled.
        hard_rock : bool, optional
            HP with the hard rock mod enabled.

        Returns
        -------
        hp : float
            The HP value.
        """
        hp = self.hp_drain_rate
        if hard_rock:
            hp = min(1.4 * hp, 10)
        elif easy:
            hp /= 2
        return hp

    def cs(self, *, easy=False, hard_rock=False):
        """Compute the Circle Size (CS) value for different mods.

        Parameters
        ----------
        easy : bool, optional
            CS with the easy mod enabled.
        hard_rock : bool, optional
            CS with the hard rock mod enabled.

        Returns
        -------
        cs : float
            The CS value.
        """
        cs = self.circle_size
        if hard_rock:
            cs = min(1.3 * cs, 10)
        elif easy:
            cs /= 2
        return cs

    def od(self,
           *,
           easy=False,
           hard_rock=False,
           half_time=False,
           double_time=False):
        """Compute the Overall Difficulty (OD) value for different mods.

        Parameters
        ----------
        easy : bool, optional
            OD with the easy mod enabled.
        hard_rock : bool, optional
            OD with the hard rock mod enabled.
        half_time : bool, optional
            Effective OD with the half time mod enabled.
        double_time : bool, optional
            Effective OD with the double time mod enabled.

        Returns
        -------
        od : float
            The OD value.
        """
        od = self.overall_difficulty
        if hard_rock:
            od = min(1.4 * od, 10)
        elif easy:
            od /= 2

        if double_time:
            od = ms_300_to_od(2 * od_to_ms_300(od) / 3)
        elif half_time:
            od = ms_300_to_od(4 * od_to_ms_300(od) / 3)

        return od

    def ar(self,
           *,
           easy=False,
           hard_rock=False,
           half_time=False,
           double_time=False):
        """Compute the Approach Rate (AR) value for different mods.

        Parameters
        ----------
        easy : bool, optional
            AR with the easy mod enabled.
        hard_rock : bool, optional
            AR with the hard rock mod enabled.
        half_time : bool, optional
            Effective AR with the half time mod enabled.
        double_time : bool, optional
            Effective AR with the double time mod enabled.

        Returns
        -------
        ar : float
            The effective AR value.

        Notes
        -----
        ``double_time`` and ``half_time`` do not actually affect the in game
        AR; however, because the map is sped up or slowed down, the effective
        approach rate is changed.
        """
        ar = self.approach_rate
        if easy:
            ar /= 2
        elif hard_rock:
            ar = min(1.4 * ar, 10)

        if double_time:
            ar = ms_to_ar(2 * ar_to_ms(ar) / 3)
        elif half_time:
            ar = ms_to_ar(4 * ar_to_ms(ar) / 3)

        return ar

    @lazyval
    def hit_objects_no_spinners(self):
        """The hit objects with spinners filtered out.
        """
        return tuple(e for e in self.hit_objects if not isinstance(e, Spinner))

    @lazyval
    def circles(self):
        """Just the circles in the beatmap.
        """
        return tuple(e for e in self.hit_objects if isinstance(e, Circle))

    @lazyval
    def max_combo(self):
        """The highest combo that can be achieved on this beatmap.
        """
        max_combo = 0

        for hit_object in self.hit_objects:
            if isinstance(hit_object, Slider):
                max_combo += hit_object.ticks
            else:
                max_combo += 1

        return max_combo

    def __repr__(self):
        return f'<{type(self).__qualname__}: {self.display_name}>'

    @classmethod
    def from_osz_path(cls, path):
        """Read a beatmap collection from an ``.osz`` file on disk.

        Parameters
        ----------
        path : str or pathlib.Path
            The file path to read from.

        Returns
        -------
        beatmaps : dict[str, Beatmap]
            A mapping from difficulty name to the parsed Beatmap.

        Raises
        ------
        ValueError
            Raised when the file cannot be parsed as a ``.osz`` file.
        """
        with ZipFile(path) as zf:
            return cls.from_osz_file(zf)

    @classmethod
    def from_path(cls, path):
        """Read in a ``Beatmap`` object from a file on disk.

        Parameters
        ----------
        path : str or pathlib.Path
            The path to the file to read from.

        Returns
        -------
        beatmap : Beatmap
            The parsed beatmap object.

        Raises
        ------
        ValueError
            Raised when the file cannot be parsed as a ``.osu`` file.
        """
        with open(path, encoding='utf-8-sig') as file:
            return cls.from_file(file)

    @classmethod
    def from_osz_file(cls, file):
        """Read a beatmap collection from a ``.osz`` file on disk.

        Parameters
        ----------
        file : zipfile.ZipFile
            The zipfile to read from.

        Returns
        -------
        beatmaps : dict[str, Beatmap]
            A mapping from difficulty name to the parsed Beatmap.

        Raises
        ------
        ValueError
            Raised when the file cannot be parsed as a ``.osz`` file.
        """
        return {
            beatmap.version: beatmap
            for beatmap in (
                Beatmap.parse(file.read(name).decode('utf-8-sig'))
                for name in
                file.namelist() if name.endswith('.osu')
            )
        }

    @classmethod
    def from_file(cls, file):
        """Read in a ``Beatmap`` object from an open file object.

        Parameters
        ----------
        file : file-like
            The file object to read from.

        Returns
        -------
        beatmap : Beatmap
            The parsed beatmap object.

        Raises
        ------
        ValueError
            Raised when the file cannot be parsed as a ``.osu`` file.
        """
        return cls.parse(file.read())

    _mapping_groups = frozenset({
        'General',
        'Editor',
        'Metadata',
        'Difficulty',
    })

    @classmethod
    def _find_groups(cls, lines):
        """Split the input data into the named groups.

        Parameters
        ----------
        lines : iterator[str]
            The raw lines from the file.

        Returns
        -------
        groups : dict[str, list[str] or dict[str, str]]
            The lines in the section. If the section is a mapping section
            the the value will be a dict from key to value.
        """
        groups = {}

        current_group = None
        group_buffer = []

        def commit_group():
            nonlocal group_buffer

            if current_group is None:
                # we are not building a group, just return
                return

            # we are currently building a group
            if current_group in cls._mapping_groups:
                # build a dict from the ``Key: Value`` line format.
                mapping = {}
                for line in group_buffer:
                    split = line.split(':', 1)
                    try:
                        key, value = split
                    except ValueError:
                        key = split[0]
                        value = ''

                    # throw away whitespace
                    mapping[key.strip()] = value.strip()
                group_buffer = mapping

            groups[current_group] = group_buffer
            group_buffer = []

        for line in lines:
            if not line or line.startswith('//'):
                # filter out empty lines and comments
                continue

            if line[0] == '[' and line[-1] == ']':
                # we found a section header, commit the current buffered group
                # and start the new group
                commit_group()
                current_group = line[1:-1]
            else:
                group_buffer.append(line)

        # commit the final group
        commit_group()
        return groups

    @classmethod
    def parse(cls, data):
        """Parse a ``Beatmap`` from text in the ``.osu`` format.

        Parameters
        ----------
        data : str
            The data to parse.

        Returns
        -------
        beatmap : Beatmap
            The parsed beatmap object.

        Raises
        ------
        ValueError
            Raised when the data cannot be parsed in the ``.osu`` format.
        """
        data = data.lstrip()
        lines = iter(data.splitlines())
        line = next(lines)
        match = cls._version_regex.match(line)
        if match is None:
            raise ValueError(f'missing osu file format specifier in: {line!r}')

        format_version = int(match.group(1))
        groups = cls._find_groups(lines)

        artist = _get_as_str(groups, 'Metadata', 'Artist')
        title = _get_as_str(groups, 'Metadata', 'Title')
        od = _get_as_float(
            groups,
            'Difficulty',
            'OverallDifficulty',
        )

        timing_points = []
        # the parent starts as None because the first timing point should
        # not be inherited
        parent = None
        for raw_timing_point in groups['TimingPoints']:
            timing_point = TimingPoint.parse(raw_timing_point, parent)
            if timing_point.parent is None:
                # we have a new parent node, pass that along to the new
                # timing points
                parent = timing_point
            timing_points.append(timing_point)

        slider_multiplier = _get_as_float(
            groups,
            'Difficulty',
            'SliderMultiplier',
            default=1.4,  # taken from wiki
        )
        slider_tick_rate = _get_as_float(
            groups,
            'Difficulty',
            'SliderTickRate',
            default=1.0,  # taken from wiki
        )

        return cls(
            format_version=format_version,
            audio_filename=_get_as_str(groups, 'General', 'AudioFilename'),
            audio_lead_in=timedelta(
                milliseconds=_get_as_int(groups, 'General', 'AudioLeadIn', 0),
            ),
            preview_time=timedelta(
                milliseconds=_get_as_int(groups, 'General', 'PreviewTime'),
            ),
            countdown=_get_as_bool(groups, 'General', 'Countdown', False),
            sample_set=_get_as_str(groups, 'General', 'SampleSet'),
            stack_leniency=_get_as_float(
                groups,
                'General',
                'StackLeniency',
                0,
            ),
            mode=GameMode(_get_as_int(groups, 'General', 'Mode', 0)),
            letterbox_in_breaks=_get_as_bool(
                groups,
                'General',
                'LetterboxInBreaks',
                False,
            ),
            widescreen_storyboard=_get_as_bool(
                groups,
                'General',
                'WidescreenStoryboard',
                False,
            ),
            bookmarks=[
                timedelta(milliseconds=ms) for ms in _get_as_int_list(
                    groups,
                    'Editor',
                    'bookmarks',
                    [],
                )
            ],
            distance_spacing=_get_as_float(
                groups,
                'Editor',
                'DistanceSpacing',
                1,
            ),
            beat_divisor=_get_as_int(groups, 'Editor', 'BeatDivisor', 4),
            grid_size=_get_as_int(groups, 'Editor', 'GridSize', 4),
            timeline_zoom=_get_as_float(groups, 'Editor', 'TimelineZoom', 1.0),
            title=title,
            title_unicode=_get_as_str(
                groups,
                'Metadata',
                'TitleUnicode',
                title,
            ),
            artist=artist,
            artist_unicode=_get_as_str(
                groups,
                'Metadata',
                'ArtistUnicode',
                artist,
            ),
            creator=_get_as_str(groups, 'Metadata', 'Creator'),
            version=_get_as_str(groups, 'Metadata', 'Version'),
            source=_get_as_str(groups, 'Metadata', 'Source', None),
            # space delimited list
            tags=_get_as_str(groups, 'Metadata', 'Tags', '').split(),
            beatmap_id=_get_as_int(groups, 'Metadata', 'BeatmapID', None),
            beatmap_set_id=_get_as_int(
                groups,
                'Metadata',
                'BeatmapSetID',
                None,
            ),
            hp_drain_rate=_get_as_float(groups, 'Difficulty', 'HPDrainRate'),
            circle_size=_get_as_float(groups, 'Difficulty', 'CircleSize'),
            overall_difficulty=_get_as_float(
                groups,
                'Difficulty',
                'OverallDifficulty',
            ),
            approach_rate=_get_as_float(
                groups,
                'Difficulty',
                'ApproachRate',
                # old maps didn't have an AR so the OD is used as a default
                default=od,
            ),
            slider_multiplier=slider_multiplier,
            slider_tick_rate=slider_tick_rate,
            timing_points=timing_points,
            hit_objects=list(map(
                partial(
                    HitObject.parse,
                    timing_points=timing_points,
                    slider_multiplier=slider_multiplier,
                    slider_tick_rate=slider_tick_rate,
                ),
                groups['HitObjects'],
            )),

        )

    def timing_point_at(self, time):
        """Get the :class:`slider.beatmap.TimingPoint` at the given time.

        Parameters
        ----------
        time : datetime.timedelta
            The time to lookup the :class:`slider.beatmap.TimingPoint` for.

        Returns
        -------
        timing_point : TimingPoint
            The :class:`slider.beatmap.TimingPoint` at the given time.
        """
        for tp in reversed(self.timing_points):
            if tp.offset <= time:
                return tp

        return self.timing_points[0]

    @staticmethod
    def _base_strain(strain):
        """Scale up the base attribute
        """
        return ((5 * np.maximum(1, strain / 0.0675) - 4) ** 3) / 100000

    @staticmethod
    def _handle_group(group):
        inner = range(1, len(group))
        for n in range(len(group)):
            for m in inner:
                if n == m:
                    continue

                a = group[n]
                b = group[m]

                ratio = a / b if a > b else b / a

                closest_power_of_two = 2 ** round(np.log2(ratio))
                offset = (
                    abs(closest_power_of_two - ratio) /
                    closest_power_of_two
                )
                yield offset ** 2

    _strain_step = timedelta(milliseconds=400)
    _decay_weight = 0.9

    def _calculate_difficulty(self, strain, difficulty_hit_objects):
        highest_strains = []
        append_highest_strain = highest_strains.append

        strain_step = self._strain_step
        interval_end = strain_step
        max_strain = 0

        previous = None
        for difficulty_hit_object in difficulty_hit_objects:
            while difficulty_hit_object.hit_object.time > interval_end:
                append_highest_strain(max_strain)

                if previous is None:
                    max_strain = 0
                else:
                    decay = (
                        _DifficultyHitObject.decay_base[strain] ** (
                            interval_end -
                            previous.hit_object.time
                        ).total_seconds()
                    )
                    max_strain = previous.strains[strain] * decay

                interval_end += strain_step

            max_strain = max(max_strain, difficulty_hit_object.strains[strain])
            previous = difficulty_hit_object

        difficulty = 0
        weight = 1

        decay_weight = self._decay_weight
        for strain in sorted(highest_strains, reverse=True):
            difficulty += weight * strain
            weight *= decay_weight

        return difficulty

    _star_scaling_factor = 0.0675
    _extreme_scaling_factor = 0.5

    @staticmethod
    def _product_no_diagonal(sequence):
        """An iterator of the Cartesian product of ``sequence`` with itself
        with the diagonals removed.

        Parameters
        ----------
        sequence : sequence
            The sequence to take the product with.

        Yields
        ------
        pair : (any, any)
            The element of the product which is not on the diagonal.
        """
        inner = range(1, len(sequence))
        for n in range(len(sequence)):
            for m in inner:
                if n == m:
                    continue

                yield sequence[n], sequence[m]

    def hit_object_difficulty(self,
                              *,
                              easy=False,
                              hard_rock=False,
                              double_time=False,
                              half_time=False):
        """Compute the difficulty of each hit object.

        Parameters
        ----------
        easy : bool
            Compute difficulty with easy.
        hard_rock : bool
            Compute difficulty with hard rock.
        double_time : bool
            Compute difficulty with double time.
        half_time : bool
            Compute difficulty with half time.

        Returns
        ----------
        times : np.ndarray
            Single column array of times as ``timedelta64[ns]``
        difficulties : np.ndarray
            Array of difficulties as ``float64``. Speed in the first column,
            aim in the second.
        """
        cs = self.cs(easy=easy, hard_rock=hard_rock)
        radius = circle_radius(cs)

        if double_time:
            modify = op.attrgetter('double_time')
        elif half_time:
            modify = op.attrgetter('half_time')
        else:
            def modify(e):
                return e

        times = np.empty(
            (len(self.hit_objects) - 1, 1),
            dtype='timedelta64[ns]',
        )
        strains = np.empty((len(self.hit_objects) - 1, 2), dtype=np.float64)

        hit_objects = map(modify, self.hit_objects)
        previous = _DifficultyHitObject(next(hit_objects), radius)
        for i, hit_object in enumerate(hit_objects):
            new = _DifficultyHitObject(
                hit_object,
                radius,
                previous,
            )
            times[i] = hit_object.time
            strains[i] = new.strains
            previous = new

        return times, strains

    def smoothed_difficulty(self,
                            smoothing_window,
                            num_points,
                            *,
                            easy=False,
                            hard_rock=False,
                            double_time=False,
                            half_time=False):
        """Calculate a smoothed difficulty at evenly spaced points in time
        between the beginning of the song and the last hit object of the map.

        Done by taking an average of difficulties of hit objects within a
        certain time window of each point

        Useful if you want to calculate a difficulty curve for the map
        since the unsmoothed values vary locally a lot.

        Parameters
        ----------
        smoothing_window : int or float
            Time window (in seconds) for the moving average.
            Bigger will make a smoother curve.
        num_points : int
            Number of points to calculate the average at.
        easy : bool
            Compute difficulty with easy.
        hard_rock : bool
            Compute difficulty with hard rock.
        double_time : bool
            Compute difficulty with double time.
        half_time : bool
            Compute difficulty with half time.

        Returns
        ----------
        difficulties : array
            2D array containing smoothed time, difficulty pairs.
        """
        times, values = self.hit_object_difficulty(
            easy=easy,
            hard_rock=hard_rock,
            double_time=double_time,
            half_time=half_time
        )

        return _moving_average_by_time(
            times,
            values,
            smoothing_window,
            num_points,
        )

    def _calculate_stars(self,
                         easy,
                         hard_rock,
                         double_time,
                         half_time):
        """Compute the stars and star components for this map.

        Parameters
        ----------
        easy : bool
            Compute stars with easy.
        hard_rock : bool
            Compute stars with hard rock.
        double_time : bool
            Compute stars with double time.
        half_time : bool
            Compute stars with half time.
        """
        cs = self.cs(easy=easy, hard_rock=hard_rock)
        radius = circle_radius(cs)

        difficulty_hit_objects = []
        append_difficulty_hit_object = difficulty_hit_objects.append

        intervals = []
        append_interval = intervals.append

        if double_time:
            modify = op.attrgetter('double_time')
        elif half_time:
            modify = op.attrgetter('half_time')
        else:
            def modify(e):
                return e

        hit_objects = map(modify, self.hit_objects)
        previous = _DifficultyHitObject(next(hit_objects), radius)
        append_difficulty_hit_object(previous)
        for hit_object in hit_objects:
            new = _DifficultyHitObject(
                hit_object,
                radius,
                previous,
            )
            append_interval(new.hit_object.time - previous.hit_object.time)
            append_difficulty_hit_object(new)
            previous = new

        group = []
        append_group_member = group.append
        clear_group = group.clear

        # todo: compute break time from ar
        break_threshhold = timedelta(milliseconds=1200)

        count_offsets = 0
        rhythm_awkwardness = 0

        for interval in intervals:
            is_break = interval >= break_threshhold

            if not is_break:
                append_group_member(interval)

            if is_break or len(group) == 5:
                for awk in self._handle_group(group):
                    count_offsets += 1
                    rhythm_awkwardness += awk

                clear_group()

        for awk in self._handle_group(group):
            count_offsets += 1
            rhythm_awkwardness += awk

        rhythm_awkwardness /= count_offsets or 1
        rhythm_awkwardness *= 82

        aim = self._calculate_difficulty(
            _DifficultyHitObject.Strain.aim,
            difficulty_hit_objects,
        )
        speed = self._calculate_difficulty(
            _DifficultyHitObject.Strain.speed,
            difficulty_hit_objects,
        )

        key = easy, hard_rock, double_time, half_time
        self._aim_stars_cache[key] = aim = (
            np.sqrt(aim) * self._star_scaling_factor
        )
        self._speed_stars_cache[key] = speed = (
            np.sqrt(speed) * self._star_scaling_factor
        )
        self._stars_cache[key] = (
            aim +
            speed +
            abs(speed - aim) *
            self._extreme_scaling_factor
        )
        self._rhythm_awkwardness_cache[key] = rhythm_awkwardness

    def _stars_cache_value(name, doc):
        """Create a cached function from pulling from the values generated
        in ``_calculate_stars``.

        Parameters
        ----------
        name : str
            The name of the attribute.
        doc : str
            The docstring for the attribute.

        Returns
        -------
        getter : function
            The getter function.
        """
        cache_name = f'_{name}_cache'

        def get(self,
                *,
                easy=False,
                hard_rock=False,
                double_time=False,
                half_time=False):
            key = (
                bool(easy),
                bool(hard_rock),
                bool(double_time),
                bool(half_time),
            )
            try:
                return getattr(self, cache_name)[key]
            except KeyError:
                self._calculate_stars(*key)

            return getattr(self, cache_name)[key]

        get.__name__ = name
        get.__doc__ = doc
        return get

    speed_stars = _stars_cache_value(
        'speed_stars',
        """The speed part of the stars.

        Parameters
        ----------
        easy : bool, optional
            Stars with the easy mod applied.
        hard_rock : bool, optional
            Stars with the hard rock mod applied.
        double_time : bool, optional
            Stars with the double time mod applied.
        half_time : bool, optional
            Stars with the half time mod applied.

        Returns
        -------
        speed_stars : float
            The aim component of the stars.
        """,
    )
    aim_stars = _stars_cache_value(
        'aim_stars',
        """The aim part of the stars.

        Parameters
        ----------
        easy : bool, optional
            Stars with the easy mod applied.
        hard_rock : bool, optional
            Stars with the hard rock mod applied.
        double_time : bool, optional
            Stars with the double time mod applied.
        half_time : bool, optional
            Stars with the half time mod applied.

        Returns
        -------
        aim_stars : float
            The aim component of the stars.
        """,
    )
    stars = _stars_cache_value(
        'stars',
        """The stars as seen in osu!.

        Parameters
        ----------
        easy : bool, optional
            Stars with the easy mod applied.
        hard_rock : bool, optional
            Stars with the hard rock mod applied.
        double_time : bool, optional
            Stars with the double time mod applied.
        half_time : bool, optional
            Stars with the half time mod applied.

        Returns
        -------
        stars : float
            The total stars for the map.
        """,
    )
    rhythm_awkwardness = _stars_cache_value(
        'rhythm_awkwardness',
        """The rhythm awkwardness component of the song.

        Parameters
        ----------
        easy : bool, optional
            Rhythm awkwardness with the easy mod applied.
        hard_rock : bool, optional
            Rhythm awkwardness with the hard rock mod applied.
        double_time : bool, optional
            Rhythm awkwardness with the double time mod applied.
        half_time : bool, optional
            Rhythm awkwardness with the half time mod applied.

        Returns
        -------
        rhythm_awkwardness : float
            The rhythm awkwardness score.
        """,
    )

    del _stars_cache_value

    def _round_hitcounts(self, accuracy, count_miss=None):
        """Round the accuracy to the nearest hit counts.

        Parameters
        ----------
        accuracy : np.ndarray[float]
            The accuracy to round in the range [0, 1]
        count_miss : np.ndarray[int]int, optional
            The number of misses to fix.

        Returns
        -------
        count_300 : np.ndarray[int]
            The number of 300s.
        count_100 : np.ndarray[int]
            The number of 100s.
        count_50 : np.ndarray[int]
            The number of 50s.
        count_miss : np.ndarray[int]
            The number of misses.
        """
        if count_miss is None:
            count_miss = np.full_like(accuracy, 0)

        max_300 = len(self.hit_objects) - count_miss

        accuracy = np.maximum(
            0.0,
            np.minimum(
                calculate_accuracy(max_300, 0, 0, count_miss) * 100.0,
                accuracy * 100,
            ),
        )

        count_50 = np.full_like(accuracy, 0)
        count_100 = np.round(
            -3.0 *
            ((accuracy * 0.01 - 1.0) * len(self.hit_objects) + count_miss) *
            0.5,
        )

        mask = count_100 > len(self.hit_objects) - count_miss
        count_100[mask] = 0
        count_50[mask] = np.round(
                -6.0 *
                ((accuracy[mask] * 0.01 - 1.0) * len(self.hit_objects) +
                 count_miss[mask]) *
                0.2,
            )
        count_50[mask] = np.minimum(max_300[mask], count_50[mask])

        count_100[~mask] = np.minimum(max_300[~mask], count_100[~mask])

        count_300 = (
            len(self.hit_objects) -
            count_100 -
            count_50 -
            count_miss
        )

        return count_300, count_100, count_50, count_miss

    def performance_points(self,
                           *,
                           combo=None,
                           accuracy=None,
                           count_300=None,
                           count_100=None,
                           count_50=None,
                           count_miss=None,
                           no_fail=False,
                           easy=False,
                           hidden=False,
                           hard_rock=False,
                           double_time=False,
                           half_time=False,
                           flashlight=False,
                           spun_out=False,
                           version=1):
        """Compute the performance points for the given map.

        Parameters
        ----------
        combo : int, optional
            The combo achieved on the map. Defaults to max combo.
        accuracy : float, optional
            The accuracy achieved in the range [0, 1]. If not provided
            and none of ``count_300``, ``count_100``, or ``count_50``
            provided then the this defaults to 100%
        count_300 : int, optional
            The number of 300s hit.
        count_100 : int, optional
            The number of 100s hit.
        count_50 : int, optional
            The number of 50s hit.
        count_miss : int, optional
            The number of misses.
        no_fail : bool, optional
            Account for no fail mod.
        easy : bool, optional
            Account for the easy mod.
        hidden : bool, optional
            Account for the hidden mod.
        hard_rock : bool, optional
            Account for the hard rock mod.
        double_time : bool, optional
            Account for the double time mod.
        half_time : bool, optional
            Account for the half time mod.
        flashlight : bool, optional
            Account for the flashlight mod.
        spun_out : bool, optional
            Account for the spun out mod.
        version : int, optional
            The version of the performance points calculation to use.

        Returns
        -------
        pp : float
            The performance points awarded for the specified play.

        Notes
        -----
        ``accuracy`` or hit counts may be passed as array-likes in which case
        the resulting ``pp`` will be a sequence of the same length. This is
        more efficient for computing PP with different results on the same
        beatmap.

        Examples
        --------
        >>> from slider.example_data.beatmaps import sendan_life
        >>> beatmap = sendan_life("Crystal's Garakowa")
        >>> # compute for 100%
        >>> beatmap.performance_points(accuracy=1.0)
        274.487178791355
        >>> # compute for 95%  accuracy
        >>> beatmap.performance_points(accuracy=0.95)
        219.09554433691147
        >>> # compute with explicit hit counts
        >>> beatmap.performance_points(
        ...     count_300=330,
        ...     count_100=2,
        ...     count_50=0,
        ...     count_miss=0,
        ... )
        265.20230843362657
        >>> # vectorized accuracy
        >>> beatmap.performance_points(
        ...     accuracy=[0.95, 0.96, 0.97, 0.98, 0.99, 1.0],
        ... )
        array([ 219.09554434,  223.67413382,  230.20890527,  239.72525216, 253.74272587,  274.48717879])
        >>> # with mods
        >>> beatmap.performance_points(
        ...     accuracy=[0.95, 0.96, 0.97, 0.98, 0.99, 1.0],
        ...     hidden=True,
        ... )
        array([ 245.0240618 ,  249.77318802,  256.50049755,  266.24423831, 280.54452189,  301.66016166])
        """  # noqa
        if version not in {1, 2}:
            raise ValueError(f'unknown PP version: {version}')

        if combo is None:
            combo = self.max_combo

        if accuracy is not None:
            if (count_300 is not None or
                    count_100 is not None or
                    count_50 is not None):
                raise ValueError('cannot pass accuracy and hit counts')
            # compute the closest hit counts for the accuracy
            accuracy = np.array(accuracy, ndmin=1, copy=False)
            count_300, count_100, count_50, count_miss = self._round_hitcounts(
                accuracy,
                np.full_like(accuracy, 0)
                if count_miss is None else
                count_miss,
            )

        elif (count_300 is None and
              count_100 is None and
              count_50 is None):
            accuracy = np.array(1.0, ndmin=1, copy=False)
            count_300, count_100, count_50, count_miss = self._round_hitcounts(
                accuracy,
                np.full_like(accuracy, 0)
                if count_miss is None else
                count_miss,
            )
        elif np.all(count_300 + count_100 + count_50 + count_miss !=
                    len(self.hit_objects)):
            s = count_300 + count_100 + count_50 + count_miss
            os = len(self.hit_objects)
            raise ValueError(
                f"hit counts don't sum to the total for the map, {s} != {os}"
            )

        od = self.od(
            easy=easy,
            hard_rock=hard_rock,
            half_time=half_time,
            double_time=double_time,
        )
        ar = self.ar(
            easy=easy,
            hard_rock=hard_rock,
            half_time=half_time,
            double_time=double_time,
        )

        accuracy_scaled = calculate_accuracy(
            count_300,
            count_100,
            count_50,
            count_miss,
        )
        accuracy = accuracy_scaled * 100
        accuracy_bonus = 0.5 + accuracy_scaled / 2

        count_hit_objects = len(self.hit_objects)
        count_hit_objects_over_2000 = count_hit_objects / 2000
        length_bonus = (
            0.95 +
            0.4 * np.minimum(1.0, count_hit_objects_over_2000) + (
                np.log10(count_hit_objects_over_2000) * 0.5
                if count_hit_objects > 2000 else
                0
            )
        )

        miss_penalty = 0.97 ** count_miss

        combo_break_penalty = combo ** 0.8 / self.max_combo ** 0.8

        ar_bonus = 1
        if ar > 10.33:
            # high ar bonus
            ar_bonus += 0.45 * (ar - 10.33)
        elif ar < 8:
            # low ar bonus
            low_ar_bonus = 0.01 * (8.0 - ar)
            if hidden:
                low_ar_bonus *= 2
            ar_bonus += low_ar_bonus

        hidden_bonus = 1.18 if hidden else 1
        flashlight_bonus = (1.45 * length_bonus) if flashlight else 1
        od_bonus = 0.98 + od ** 2 / 2500

        mods = {
            'easy': easy,
            'hard_rock': hard_rock,
            'half_time': half_time,
            'double_time': double_time,
        }
        aim_score = (
            self._base_strain(self.aim_stars(**mods)) *
            length_bonus *
            miss_penalty *
            combo_break_penalty *
            ar_bonus *
            accuracy_bonus *
            hidden_bonus *
            flashlight_bonus *
            od_bonus
        )

        speed_score = (
            self._base_strain(self.speed_stars(**mods)) *
            length_bonus *
            miss_penalty *
            combo_break_penalty *
            accuracy_bonus *
            od_bonus
        )

        if version == 2:
            count_circles = count_hit_objects
            real_accuracy = accuracy
        else:
            count_circles = len(self.circles)
            if count_circles:
                real_accuracy = (
                    (count_300 - (count_hit_objects - count_circles)) * 300.0 +
                    count_100 * 100.0 +
                    count_50 * 50.0
                ) / (count_circles * 300)
                real_accuracy = np.maximum(real_accuracy, 0)
            else:
                real_accuracy = 0

        accuracy_length_bonus = min(1.5, (count_circles / 1000) ** 0.3)
        accuracy_hidden_bonus = 1.02 if hidden else 1
        accuracy_flashlight_bonus = 1.02 if flashlight else 1
        accuracy_score = (
            1.52163 ** od * real_accuracy ** 24.0 * 2.83 *
            accuracy_length_bonus *
            accuracy_hidden_bonus *
            accuracy_flashlight_bonus
        )

        final_multiplier = 1.12
        if no_fail:
            final_multiplier *= 0.9
        if spun_out:
            final_multiplier *= 0.95

        out = (
            (aim_score ** 1.1) +
            (speed_score ** 1.1) +
            (accuracy_score ** 1.1)
        ) ** (1 / 1.1) * final_multiplier

        if np.shape(out) == (1,):
            out = np.asscalar(out)

        return out
