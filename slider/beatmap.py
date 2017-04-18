from datetime import timedelta
import re
import warnings
from zipfile import ZipFile

from .game_mode import GameMode
from .position import Position


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
    inherited : bool
        Is this an inherited timing point? An inherited timing point differs
        from a Timing point in that the ms_per_beat value is negative, and
        defines a new ms_per_beat based on the last non-inherited timing point.
        This can be used to change volume without affecting offset timing, or
        changing slider speeds.
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
                 inherited,
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
        self.inherited = inherited
        self.kiai_mode = kiai_mode

    def __repr__(self):
        return (
            f'<{type(self).__qualname__}:'
            f' {self.offset.total_seconds() * 1000:g}ms>'
        )

    @classmethod
    def parse(cls, data):
        """Parse a TimingPoint object from a line in a ``.osu`` file.

        Parameters
        ----------
        data : str
            The line to parse.

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
            inherited=inherited,
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

    @classmethod
    def parse(cls, data):
        """Parse a HitObject object from a line in a ``.osu`` file.

        Parameters
        ----------
        data : str
            The line to parse.

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
            type_ob = Circle
        elif type_ & Slider.type_code:
            type_ob = Slider
        elif type_ & Spinner.type_code:
            type_ob = Spinner
        elif type_ & HoldNote.type_code:
            type_ob = HoldNote
        else:
            raise ValueError(f'unknown type code {type_!r}')

        return type_ob._parse(Position(x, y), time, hitsound, rest)


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
    time : int
        When this slider appears in the map.
    hitsound : int
        The sound played on the tickss of the slider.
    slider_type : {'L', 'B', 'P', 'C'}
        The type of slider. Linear, Bezier, Perfect, and Catmull.
    points : iterable[Position]
        The points that this slider travels through.
    length : int
        The length of this slider in osu! pixels.
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
                 hitsound,
                 slider_type,
                 points,
                 repeat,
                 length,
                 edge_sounds,
                 edge_additions,
                 addition='0:0:0:0'):
        if slider_type not in {'L', 'B', 'P', 'C'}:
            raise ValueError(
                "slider_type should be in {'L', 'B', 'P', 'C'},"
                f" got {slider_type!r}",
            )

        super().__init__(position, time, hitsound, addition)
        self.slider_type = slider_type
        self.points = points
        self.repeat = repeat
        self.length = length
        self.edge_sounds = edge_sounds
        self.edge_additions = edge_additions

    @classmethod
    def _parse(cls, position, time, hitsound, rest):
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

        return cls(
            position,
            time,
            hitsound,
            slider_type,
            points,
            repeat,
            pixel_length,
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

    @property
    def hp(self):
        return self.hp_drain_rate

    @property
    def cs(self):
        return self.circle_size

    @property
    def od(self):
        return self.overall_difficulty

    @property
    def ar(self):
        return self.approach_rate

    @property
    def hit_objects_no_spinners(self):
        return tuple(e for e in self.hit_objects if not isinstance(e, Spinner))

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
            slider_multiplier=_get_as_float(
                groups,
                'Difficulty',
                'SliderMultiplier',
                default=1.4,  # taken from wiki
            ),
            slider_tick_rate=_get_as_float(
                groups,
                'Difficulty',
                'SliderTickRate',
                default=1.0,  # taken from wiki
            ),
            timing_points=list(map(TimingPoint.parse, groups['TimingPoints'])),
            hit_objects=list(map(HitObject.parse, groups['HitObjects'])),
        )
