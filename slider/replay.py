import datetime
from enum import unique
import os
import lzma

from .bit_enum import BitEnum
from .game_mode import GameMode
from .mod import Mod
from .position import Position
from .utils import accuracy, lazyval


@unique
class ActionBitMask(BitEnum):
    """The bitmask values for the action type.
    """
    m1 = 1
    m2 = 2
    k1 = 5
    k2 = 10


class Action:
    """A user action.

    Parameters
    ----------
    offset : timedelta
        The offset since the previous action.
    position : Position
        The position of the cursor.
    key1 : bool
        Is the first keyboard key pressed?
    key2 : bool
        Is the second keyboard key pressed?
    mouse1 : bool
        Is the first mouse button pressed?
    mouse2 : bool
        is the second mouse button pressed?
    """
    def __init__(self, offset, position, key1, key2, mouse1, mouse2):
        self.offset = offset
        self.position = position
        self.key1 = key1
        self.key2 = key2
        self.mouse1 = mouse1
        self.mouse2 = mouse2

    @property
    def action_bitmask(self):
        """Get the action bitmask from an action.
        """
        return ActionBitMask.pack(
            m1=self.mouse1,
            m2=self.mouse2,
            k1=self.key1,
            k2=self.key2,
        )


def _consume_byte(buffer):
    result = buffer[0]
    del buffer[0]
    return result


def _consume_short(buffer):
    result = int.from_bytes(buffer[:2], 'little')
    del buffer[:2]
    return result


def _consume_int(buffer):
    result = int.from_bytes(buffer[:4], 'little')
    del buffer[:4]
    return result


def _consume_long(buffer):
    result = int.from_bytes(buffer[:8], 'little')
    del buffer[:8]
    return result


def _consume_uleb128(buffer):
    result = 0
    shift = 0
    while True:
        byte = _consume_byte(buffer)
        result |= (byte & 0x7f) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7

    return result


def _consume_string(buffer):
    mode = _consume_byte(buffer)
    if mode == 0:
        return None
    if mode != 0x0b:
        raise ValueError(
            f'unknown string start byte: {hex(mode)}, expected 0 or 0x0b',
        )
    byte_length = _consume_uleb128(buffer)
    data = buffer[:byte_length]
    del buffer[:byte_length]
    return data.decode('utf-8')


_windows_epoch = datetime.datetime(1, 1, 1)


def _consume_datetime(buffer):
    windows_ticks = _consume_long(buffer)
    return _windows_epoch + datetime.timedelta(microseconds=windows_ticks / 10)


def _consume_life_bar_graph(buffer):
    life_bar_graph_raw = _consume_string(buffer)
    return [
        (datetime.timedelta(milliseconds=int(offset)), float(value))
        for offset, value in (
            pair.split('|') for pair in life_bar_graph_raw.split(',') if pair
        )
    ]


def _consume_actions(buffer):
    compressed_byte_count = _consume_int(buffer)
    compressed_data = buffer[:compressed_byte_count]
    del buffer[:compressed_byte_count]
    decompressed_data = lzma.decompress(compressed_data)

    out = []
    for raw_action in decompressed_data.split(b','):
        if not raw_action:
            continue
        offset, x, y, raw_action_mask = raw_action.split(b'|')
        action_mask = ActionBitMask.unpack(int(raw_action_mask))
        out.append(Action(
            datetime.timedelta(milliseconds=int(offset)),
            Position(float(x), float(y)),
            action_mask['m1'],
            action_mask['m2'],
            action_mask['k1'],
            action_mask['k2'],
        ))


class Replay:
    """An osu! replay.

    Parameters
    ----------
    mode : GameMode
        The game mode.
    version : int
        The version of osu! used to create this replay.
    beatmap_md5 : str
        The md5 hash of the beatmap played in this replay.
    player_name : str
        The name of the player who recorded this replay.
    replay_md5 : str
        The md5 hash of part of the data in this replay.
    count_300 : int
        The number of 300's hit in the replay.
    count_100 : int
        The number of 100's hit in the replay.
    count_50 : int
        The number of 50's hit in the replay.
    count_geki : int
        The number of geki in the replay. A geki is when the user scores all
        300's for a given color section.
    count_katu : int
        The number of katu in the replay. A katu is when the user completes
        a given color section without any 50's or misses. All 300's would
        result in a geki instead of a katu.
    count_miss : int
        The number of misses in the replay.
    score : int
        The score earned in this replay. This is the normal score, not
        performance points.
    max_combo : int
        The largest combo achieved in this replay.
    full_combo : bool
        Did the player earn a max combo in this replay?
    no_fail : bool
        Was the no_fail mod used?
    easy : bool
        Was the easy mod used?
    no_video : bool
        Was the no_video mod used?
    hidden : bool
        Was the hidden mod used?
    hard_rock : hard_rock
        Was the hard_rock mod used?
    sudden_death : bool
        Was the sudden_death mod used?
    double_time : bool
        Was the double_time mod used?
    relax : bool
        Was the relax mod used?
    half_time : bool
        Was the half_time mod used?
    nightcore : bool
        Was the nightcore mod used?
    flashlight : bool
        Was the flashlight mod used?
    autoplay : bool
        Was the autoplay mod used?
    spun_out : bool
        Was the spun_out mod used?
    auto_pilot : bool
        Was the auto_pilot mod used?
    perfect : bool
        Was the perfect mod used?
    key4 : bool
        Was the key4 mod used?
    key5 : bool
        Was the key5 mod used?
    key6 : bool
        Was the key6 mod used?
    key7 : bool
        Was the key7 mod used?
    key8 : bool
        Was the key8 mod used?
    fade_in : bool
        Was the fade_in mod used?
    random : bool
        Was the random mod used?
    cinema : bool
        Was the cinema mod used?
    target_practice : bool
        Was the target_practice mod used?
    key9 : bool
        Was the key9 mod used?
    coop : bool
        Was the coop mod used?
    key1 : bool
        Was the key1 mod used?
    key3 : bool
        Was the key3 mod used?
    key2 : bool
        Was the key2 mod used?
    scoreV2 : bool
        Was the scoreV2 mod used?
    life_bar_graph : list[timedelta, float]
        A list of time points paired with the value of the life bar at that
        time. These appear in sorted order. The values are in the range [0, 1].
    timestamp : datetime
        When this replay was created.
    actions : list[Action]
        A sorted list of all of the actions recorded from the player.
    beatmap : Beatmap or None
        The beatmap played in this replay if known, otherwise None.
    """
    def __init__(self,
                 mode,
                 version,
                 beatmap_md5,
                 player_name,
                 replay_md5,
                 count_300,
                 count_100,
                 count_50,
                 count_geki,
                 count_katu,
                 count_miss,
                 score,
                 max_combo,
                 full_combo,
                 no_fail,
                 easy,
                 no_video,
                 hidden,
                 hard_rock,
                 sudden_death,
                 double_time,
                 relax,
                 half_time,
                 nightcore,
                 flashlight,
                 autoplay,
                 spun_out,
                 auto_pilot,
                 perfect,
                 key4,
                 key5,
                 key6,
                 key7,
                 key8,
                 fade_in,
                 random,
                 cinema,
                 target_practice,
                 key9,
                 coop,
                 key1,
                 key3,
                 key2,
                 scoreV2,
                 life_bar_graph,
                 timestamp,
                 actions,
                 beatmap):
        self.mode = mode
        self.version = version
        self.beatmap_md5 = beatmap_md5
        self.player_name = player_name
        self.replay_md5 = replay_md5
        self.count_300 = count_300
        self.count_100 = count_100
        self.count_50 = count_50
        self.count_geki = count_geki
        self.count_katu = count_katu
        self.count_miss = count_miss
        self.score = score
        self.max_combo = max_combo
        self.full_combo = full_combo
        self.no_fail = no_fail
        self.easy = easy
        self.no_video = no_video
        self.hidden = hidden
        self.hard_rock = hard_rock
        self.sudden_death = sudden_death
        self.double_time = double_time
        self.relax = relax
        self.half_time = half_time
        self.nightcore = nightcore
        self.flashlight = flashlight
        self.autoplay = autoplay
        self.spun_out = spun_out
        self.auto_pilot = auto_pilot
        self.perfect = perfect
        self.key4 = key4
        self.key5 = key5
        self.key6 = key6
        self.key7 = key7
        self.key8 = key8
        self.fade_in = fade_in
        self.random = random
        self.cinema = cinema
        self.target_practice = target_practice
        self.key9 = key9
        self.coop = coop
        self.key1 = key1
        self.key3 = key3
        self.key2 = key2
        self.scoreV2 = scoreV2
        self.life_bar_graph = life_bar_graph
        self.timestamp = timestamp
        self.actions = actions
        self.beatmap = beatmap

    @lazyval
    def accuracy(self):
        """The accuracy achieved in the replay in the range [0, 1].
        """
        if self.mode != GameMode.standard:
            raise NotImplementedError(
                'accuracy for non osu!standard replays is not yet supported',
            )

        return accuracy(
            self.count_300,
            self.count_100,
            self.count_50,
            self.count_miss,
        )

    @lazyval
    def performance_points(self):
        return self.beatmap.performance_points(
            count_300=self.count_300,
            count_100=self.count_100,
            count_50=self.count_50,
            count_miss=self.count_miss,
            easy=self.easy,
            hard_rock=self.hard_rock,
            half_time=self.half_time,
            double_time=self.double_time,
            hidden=self.hidden,
            flashlight=self.flashlight,
            spun_out=self.spun_out,
        )

    @classmethod
    def from_path(cls, path, *, library=None, client=None, save=False):
        """Read in a ``Replay`` object from a ``.osr`` file on disk.

        Parameters
        ----------
        path : str or pathlib.Path
            The path to the file to read from.
        library : Library, optional
            The library of beatmaps.
        client : Client, optional.
            The client used to find the beatmap.
        save : bool, optional
            If the beatmap needs to be downloaded with the client, should it be
            saved to disk?

        Returns
        -------
        replay : Replay
            The parsed replay object.

        Raises
        ------
        ValueError
            Raised when the file cannot be parsed as an ``.osr`` file.
        """
        with open(path, 'rb') as f:
            return cls.from_file(f, library=library, client=client, save=save)

    @classmethod
    def from_directory(cls, path, *, library=None, client=None, save=False):
        """Read in a list of ``Replay`` objects from a directory of ``.osr``
        files.

        Parameters
        ----------
        path : str or pathlib.Path
            The path to the directory to read from.
        library : Library, optional
            The library of beatmaps.
        client : Client, optional.
            The client used to find the beatmap.
        save : bool, optional
            If the beatmap needs to be downloaded with the client, should it be
            saved to disk?

        Returns
        -------
        replays : list[Replay]
            The parsed replay objects.

        Raises
        ------
        ValueError
            Raised when any file cannot be parsed as an ``.osr`` file.
        """
        return [
            cls.from_path(p, library, client=client, save=save)
            for p in os.scandir(path)
            if p.name.endswith('.osr')
        ]

    @classmethod
    def from_file(cls, file, *, library=None, client=None, save=False):
        """Read in a ``Replay`` object from an open file object.

        Parameters
        ----------
        file : file-like
            The file object to read from.
        library : Library, optional
            The library of beatmaps.
        client : Client, optional.
            The client used to find the beatmap.
        save : bool, optional
            If the beatmap needs to be downloaded with the client, should it be
            saved to disk?

        Returns
        -------
        replay : Replay
            The parsed replay object.

        Raises
        ------
        ValueError
            Raised when the file cannot be parsed as a ``.osr`` file.
        """
        return cls.parse(
            file.read(),
            library=library,
            client=client,
            save=save,
        )

    @classmethod
    def parse(cls, data, *, library=None, client=None, save=False):
        """Parse a replay from ``.osr`` file data.

        Parameters
        ----------
        data : bytes
            The data from an ``.osr`` file.

        Returns
        -------
        replay : Replay
            The parsed replay.
        library : Library, optional
            The library of beatmaps.
        client : Client, optional.
            The client used to find the beatmap.
        save : bool, optional
            If the beatmap needs to be downloaded with the client, should it be
            saved to disk?

        Raises
        ------
        ValueError
            Raised when ``data`` is not in the ``.osr`` format.
        """
        if library is None and client is None:
            raise ValueError('one of library or client must be passed')

        use_client = client is not None
        if use_client:
            if library is not None:
                raise ValueError('only one of library or client can be passed')
            library = client.library

        buffer = bytearray(data)

        mode = GameMode(_consume_byte(buffer))
        version = _consume_int(buffer)
        beatmap_md5 = _consume_string(buffer)
        player_name = _consume_string(buffer)
        replay_md5 = _consume_string(buffer)
        count_300 = _consume_short(buffer)
        count_100 = _consume_short(buffer)
        count_50 = _consume_short(buffer)
        count_geki = _consume_short(buffer)
        count_katu = _consume_short(buffer)
        count_miss = _consume_short(buffer)
        score = _consume_int(buffer)
        max_combo = _consume_short(buffer)
        full_combo = bool(_consume_byte(buffer))
        mod_mask = _consume_int(buffer)
        life_bar_graph = _consume_life_bar_graph(buffer)
        timestamp = _consume_datetime(buffer)
        actions = _consume_actions(buffer)

        mod_kwargs = Mod.unpack(mod_mask)
        # delete the alias field names
        del mod_kwargs['relax2']
        del mod_kwargs['last_mod']

        try:
            beatmap = library.lookup_by_md5(beatmap_md5)
        except KeyError:
            if not use_client:
                raise
            beatmap = client.beatmap(
                beatmap_md5=beatmap_md5,
            ).beatmap(save=save)

        return cls(
            mode=mode,
            version=version,
            beatmap_md5=beatmap_md5,
            player_name=player_name,
            replay_md5=replay_md5,
            count_300=count_300,
            count_100=count_100,
            count_50=count_50,
            count_geki=count_geki,
            count_katu=count_katu,
            count_miss=count_miss,
            score=score,
            max_combo=max_combo,
            full_combo=full_combo,
            life_bar_graph=life_bar_graph,
            timestamp=timestamp,
            actions=actions,
            beatmap=beatmap,
            **mod_kwargs,
        )

    def __repr__(self):
        try:
            accuracy = f'{self.accuracy * 100:.2f}'
        except NotImplementedError:
            accuracy = '<unknown>'

        beatmap = self.beatmap
        if beatmap is None:
            beatmap = '<unknown>'

        return (
            f'<{type(self).__qualname__}: {accuracy}% ('
            f'{self.count_300}/{self.count_100}/'
            f'{self.count_50}/{self.count_miss}) on {beatmap}>'
        )
