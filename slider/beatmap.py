from datetime import timedelta
from functools import partial
import operator as op
import re
from zipfile import ZipFile

from .game_mode import GameMode
from .mod import ar_to_ms, ms_to_ar, circle_radius
from .position import Position
from .utils import accuracy as calculate_accuracy, lazyval

try:
    import numpy as np
except ModuleNotFoundError:
    from math import log10, ceil
else:
    max = np.max
    min = np.min
    log10 = np.log10
    ceil = np.ceil


class _no_default:
    """Sentinel type; this should not be instantiated.

    This type is used so functions can tell the difference between no argument
    passed and an explicit value passed even if ``None`` is a valid value.

    Notes
    -----
    This is implemented as a type to make functions which use this as a default
    argument serializable.
    """
    def __new__(cls):
        raise TypeError('cannot create instances of sentinel type')


def _get(cs, ix, default=_no_default):
    try:
        return cs[ix]
    except IndexError:
        if default is _no_default:
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
        The volume of hit sounds in the range [0, 100].
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
        if not (0 <= volume <= 100):
            raise ValueError(
                f'volume must be in the range [0, 100], got {volume!r}',
            )
        self.offset = offset
        self.ms_per_beat = ms_per_beat
        self.meter = meter
        self.sample_type = sample_type
        self.sample_set = sample_set
        self.volume = volume
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
        return (
            f'<{type(self).__qualname__}:'
            f' {self.offset.total_seconds() * 1000:g}ms>'
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

    @lazyval
    def half_time(self):
        """The ``HitObject`` as it would appear with
        :data:`~slider.mod.Mod.half_time` enabled.
        """
        kwargs = vars(self)
        kwargs['time'] = 4 * kwargs['time'] / 3
        try:
            end_time = kwargs['end_time']
        except KeyError:
            pass
        else:
            kwargs['end_time'] = 4 * end_time / 3
        return type(self)(**kwargs)

    @lazyval
    def double_time(self):
        """The ``HitObject`` as it would appear with
        :data:`~slider.mod.Mod.double_time` enabled.
        """
        kwargs = vars(self)
        kwargs['time'] = 2 * kwargs['time'] / 3
        kwargs['time'] = 4 * kwargs['time'] / 3
        try:
            end_time = kwargs['end_time']
        except KeyError:
            pass
        else:
            kwargs['end_time'] = 2 * end_time / 3
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
    time : int
        When this spinner appears in the map.
    end_time : int
        When this spinner ends in the map.
    addition : str
        Hitsound additions.
    """
    type_code = 8

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
            end_time = int(end_time)
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
    slider_type : {'L', 'B', 'P', 'C'}
        The type of slider. Linear, Bezier, Perfect, and Catmull.
    points : iterable[Position]
        The points that this slider travels through.
    length : int
        The length of this slider in osu! pixels.
    ticks : int
        The number of slider ticks including the head and tail of the slider.
    edge_sounds : list[int]
        A list of hitsounds for each edge.
    edge_additions : list[str]
        A list of additions for each edge.
    addition : str
        Hitsound additions.
    """
    type_code = 2

    def __init__(self,
                 position,
                 time,
                 end_time,
                 hitsound,
                 slider_type,
                 points,
                 repeat,
                 length,
                 ticks,
                 edge_sounds,
                 edge_additions,
                 addition='0:0:0:0'):
        if slider_type not in {'L', 'B', 'P', 'C'}:
            raise ValueError(
                "slider_type should be in {'L', 'B', 'P', 'C'},"
                f" got {slider_type!r}",
            )

        super().__init__(position, time, hitsound, addition)
        self.end_time = end_time
        self.slider_type = slider_type
        self.points = points
        self.repeat = repeat
        self.length = length
        self.ticks = ticks
        self.edge_sounds = edge_sounds
        self.edge_additions = edge_additions

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

        points = []
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

        for tp in timing_points:
            if tp.offset < time:
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
        num_beats = (pixel_length * repeat) / pixels_per_beat
        duration = timedelta(milliseconds=ceil(num_beats * ms_per_beat))

        ticks = int(
            ((ceil(num_beats / repeat * slider_tick_rate) - 1) * repeat) +
            repeat +
            1
        )

        return cls(
            position,
            time,
            time + duration,
            hitsound,
            slider_type,
            points,
            repeat,
            pixel_length,
            ticks,
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


def _get_as_str(groups, section, field, default=_no_default):
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
        if default is _no_default:
            raise ValueError(f'missing section {section!r}')
        return default

    try:
        return mapping[field]
    except KeyError:
        if default is _no_default:
            raise ValueError(f'missing field {field!r} in section {section!r}')
        return default


def _get_as_int(groups, section, field, default=_no_default):
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


def _get_as_int_list(groups, section, field, default=_no_default):
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


def _get_as_float(groups, section, field, default=_no_default):
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


def _get_as_bool(groups, section, field, default=_no_default):
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

    @lazyval
    def bpm_min(self):
        """The minimum bpm in this beatmap.
        """
        # use list comprehension for when this is np.min
        return min([p.bpm for p in self.timing_points if p.bpm])

    @lazyval
    def bpm_max(self):
        """The maximum bpm in this beatmap.
        """
        # use list comprehension for when this is np.max
        return max([p.bpm for p in self.timing_points if p.bpm])

    @lazyval
    def hp(self):
        """Alias for ``hp_drain_rate``.
        """
        return self.hp_drain_rate

    @lazyval
    def cs(self):
        """Alias for ``circle_size``.
        """
        return self.circle_size

    @lazyval
    def od(self):
        """Alias for ``overall_difficulty``.
        """
        return self.overall_difficulty

    @lazyval
    def ar(self):
        """Alias for ``approach_rate``.
        """
        return self.approach_rate

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
        return f'<{type(self).__qualname__}: {self.title} [{self.version}]>'

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
            Raised when the file cannot be pased as a ``.osz`` file.
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
            Raised when the file cannot be pased as a ``.osz`` file.
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
                    key, value = line.split(':', 1)
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
            if parent is not None and timing_point.parent is None:
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
                milliseconds=_get_as_int(groups, 'General', 'AudioLeadIn'),
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
        for tp in self.timing_points:
            if tp.offset < time:
                return tp

        return self.timing_points[0]

    @staticmethod
    def _base_strain(strain):
        """Scale up the base attribute
        """
        return ((5 * max(1, strain / 0.0675) - 4) ** 3) / 100000

    def _star_calc(self):
        # radius = circle_radius(self.cs)

        # hit_objects = iter(self.hit_objects)
        # previous = next(hit_objects)
        # for hit_object in hit_objects:
        #     ...

        raise NotImplementedError('_star_calc')

    def _round_hitcounts(self, accuracy, count_miss=0):
        """Round the accuracy to the nearest hit counts.

        Parameters
        ----------
        accuracy : float
            The accuracy to round in the range [0, 1]
        count_miss : int, optional
            The number of misses to fix.

        Returns
        -------
        count_300 : int
            The number of 300s.
        count_100 : int
            The number of 100s.
        count_50 : int
            The number of 50s.
        count_miss : int
            The number of misses.
        """
        max_300 = len(self.hit_objects) - count_miss

        accuracy = max(
            0.0,
            min(
                calculate_accuracy(max_300, 0, 0, count_miss) * 100.0,
                accuracy * 100,
            ),
        )

        count_50 = 0
        count_100 = round(
            -3.0 *
            ((accuracy * 0.01 - 1.0) * len(self.hit_objects) + count_miss) *
            0.5,
        )

        if count_100 > len(self.hit_objects) - count_miss:
            # accuracy lower than all 100s, use 50s
            count_100 = 0
            count_50 = round(
                -6.0 *
                ((accuracy * 0.01 - 1.0) * len(self.hit_objects) +
                 count_miss) *
                0.2,
            )

            count_50 = min(max_300, count_50)
        else:
            count_100 = min(max_300, count_100)

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
                           count_miss=0,
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
        """
        raise NotImplementedError('pp calculation is not done')

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
            count_300, count_100, count_50, count_miss = self._round_hitcounts(
                accuracy,
                count_miss,
            )

        elif (count_300 is None and
              count_100 is None and
              count_50 is not None):
            count_300, count_100, count_50, count_miss = self._round_hitcounts(
                accuracy,
                count_miss,
            )

        od = self.od
        ar = self.ar

        if easy:
            od /= 2
            ar /= 2
        elif hard_rock:
            od = min(1.4 * od, 10)
            ar = min(1.4 * ar, 10)

        if half_time:
            ar = ms_to_ar(4 * ar_to_ms(ar) / 3)
        elif double_time:
            ar = ms_to_ar(2 * ar_to_ms(ar) / 3)

        accuracy = calculate_accuracy(
            count_300,
            count_100,
            count_50,
            count_miss,
        ) * 100
        accuracy_bonus = 0.5 + accuracy / 2

        count_hit_objects = len(self.hit_objects)
        count_hit_objects_over_2000 = count_hit_objects / 2000
        length_bonus = (
            0.95 +
            0.4 * min(1.0, count_hit_objects_over_2000) + (
                log10(count_hit_objects_over_2000) * 0.5
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
        flashlight_bonus = 1.45 * length_bonus if flashlight else 1
        od_bonus = 0.98 + od ** 2 / 2500

        aim_score = (
            self._base_strain(self.aim_stars) *
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
            self._base_strain(self.speed_stars) *
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
                real_accuracy = max(real_accuracy, 0)
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

        return (
            (aim_score ** 1.1) +
            (speed_score ** 1.1) +
            (accuracy_score ** 1.1)
        ) ** (1 / 1.1) * final_multiplier
