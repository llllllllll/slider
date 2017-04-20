import datetime
from enum import IntEnum, unique

import pytz
import requests

from .beatmap import Beatmap


@unique
class ApprovedState(IntEnum):
    """The state of a beatmap's approval.
    """
    loved = 4
    qualified = 3
    approved = 2
    ranked = 1
    pending = 0
    WIP = -1
    graveyard = -2


@unique
class Genre(IntEnum):
    """The genres that appear on the osu! website.
    """
    any = 0
    unspecified = 1
    video_game = 2
    anime = 3
    rock = 4
    pop = 5
    other = 6
    novelty = 7
    # note: there is no 8
    hip_hop = 9
    electronic = 10


@unique
class Language(IntEnum):
    """The languages that appear on the osu! website.
    """
    any = 0
    other = 1
    english = 2
    japanese = 3
    chinese = 4
    instrumental = 5
    korean = 6
    french = 7
    german = 8
    swedish = 9
    spanish = 10
    italian = 11


class BeatmapResult:
    """A beatmap as represented by the osu! API.

    Parameters
    ----------
    beatmap : Beatmap
        The beatmap object.
    approved : ApprovedState
        The state of the beatmap's approved.
    approved_date : datetime.datetime
        The date when this map was approved.
    last_update : datetime.datetime
        The last date when this map was updated.
    star_rating : float
        The star rating for the song.
    hit_length : datetime.timedelta
        The amount of time from the first element to the last, not counting
        breaks.
    genre : Genre
        The genre that appears on the osu! website.
    language : Language
        The language that appears on the osu! website.
    total_length : datetime.timedelta
        The amount of time from the first element to the last, counting breaks.
    beatmap_md5 : str
        The md5 hash of the beatmap.
    favourite_count : int
        The number of times the beatmap has been favorited.
    play_count : int
        The number of times this beatmap has been played.
    pass_count : int
        The number of times this beatmap has been passed.
    max_combo : int
        The maximum combo that could be achieved on this beatmap.
    """
    def __init__(self,
                 beatmap,
                 approved,
                 approved_date,
                 last_update,
                 star_rating,
                 hit_length,
                 genre,
                 language,
                 total_length,
                 beatmap_md5,
                 favourite_count,
                 play_count,
                 pass_count,
                 max_combo):
        self.beatmap = beatmap
        self.approved = approved
        self.approved_date = approved_date
        self.last_update = last_update
        self.star_rating = star_rating
        self.hit_length = hit_length
        self.genre = genre
        self.language = language
        self.total_length = total_length
        self.beatmap_md5 = beatmap_md5
        self.favourite_count = favourite_count
        self.play_count = play_count
        self.pass_count = pass_count
        self.max_combo = max_combo

    def __repr__(self):
        return (
            f'<{type(self).__qualname__}: {self.beatmap.title}'
            f' [{self.beatmap.version}]>'
        )


class Client:
    """A client for interacting with the osu! rest API.

    Parameters
    ----------
    api_key : str
        The api key to use.
    """
    def __init__(self, api_key, api_url='https://osu.ppy.sh/'):
        self.api_key = api_key
        self.api_url = api_url

    # differences in the osu! api names and slider's names
    _beatmap_aliases = {
        'beatmapset_id': 'beatmap_set_id',
        'difficultyrating': 'star_rating',
        'diff_size': 'circle_size',
        'diff_overall': 'overall_difficulty',
        'diff_approach': 'approach_rate',
        'diff_drain': 'health_drain',
        'genre_id': 'genre',
        'language_id': 'language',
        'file_md5': 'beatmap_md5',
        'playcount': 'play_count',
        'passcount': 'pass_count',
    }

    def _parse_date(cs, *, _tz=pytz.FixedOffset(8 * 60)):
        # _tz is UTC+8
        return _tz.localize(
            datetime.datetime.strptime(cs, '%Y-%m-%f %H:%M:%S'),
        )

    def _parse_timedelta(cs):
        return datetime.timedelta(seconds=int(cs))

    def _identity(cs):
        return cs

    _beatmap_conversions = {
        'approved': lambda cs: ApprovedState(int(cs)),
        'approved_date': _parse_date,
        'last_update': _parse_date,
        'beatmap_id': int,
        'star_rating': float,
        'hit_length': _parse_timedelta,
        'genre': lambda cs: Genre(int(cs)),
        'language': lambda cs: Language(int(cs)),
        'total_length': _parse_timedelta,
        'beatmap_md5': _identity,
        'favourite_count': int,
        'play_count': int,
        'pass_count': int,
        'max_combo': int,
    }

    del _parse_timedelta
    del _parse_date

    def beatmap(self,
                *,
                since=None,
                beatmap_set_id=None,
                beatmap_id=None,
                beatmap_md5=None,
                user_id=None,
                user_name=None,
                game_mode=None,
                include_converted_beatmaps=False,
                limit=500):
        """Retrieve information about a beatmap or set of beatmaps from the
        osu! API.

        Parameters
        ----------
        since : datetime.date, optional
            Return all beatmaps ranked since this date.
        beatmap_set_id : str, optional
            Return all beatmaps in this set.
        beatmap_id : str, optional
            Return the single beatmap with the given id.
        beatmap_md5 : str, optional
            Return the single beatmap with the given hash.
        user_id : int, optional
            Return beatmaps made by the given user.
        user_name : str, optional
            Return beatmaps made by the given user.
        game_mode : GameMode, optional
            Return beatmaps for the given game mode.
        include_converted_beatmaps : bool, optional
            Return converted beatmaps. This only applies for non-osu!standard
            game modes.
        limit : int, optional
            The maximum number of beatmaps to return. This must be less than
            500.
        """
        beatmap_identifiers = {
            k: v for k, v in {
                'beatmap_set_id': beatmap_set_id,
                'beatmap_id': beatmap_id,
                'beatmap_md5': beatmap_md5,
            }.items()
            if v is not None
        }
        if len(beatmap_identifiers) > 1:
            raise ValueError(
                f'only one of beatmap_set_id, beatmap_id, or beatmap_md5 can'
                f' be passed, got {beatmap_identifiers!r}',
            )
        if user_name is not None and user_id is not None:
            raise ValueError('only one of user_name or user_id can be passed')

        if limit > 500:
            raise ValueError('only 500 beatmaps can be requested at one time')

        parameters = {
            'k': self.api_key,
            'a': include_converted_beatmaps,
            'limit': limit,
        }

        if since is not None:
            parameters['since'] = since.isoformat()

        if beatmap_set_id is not None:
            parameters['s'] = beatmap_set_id
        elif beatmap_id is not None:
            parameters['b'] = beatmap_id
        elif beatmap_md5 is not None:
            parameters['h'] = beatmap_md5

        if user_id is not None:
            parameters['u'] = user_id
            parameters['type'] = 'id'
        elif user_name is not None:
            parameters['u'] = user_name
            parameters['type'] = 'string'

        if game_mode is not None:
            parameters['m'] = game_mode

        response = requests.get(
            self.api_url + '/api/get_beatmaps',
            params=parameters,
        )
        response.raise_for_status()

        as_dicts = (
            {self._beatmap_aliases.get(k, k): v for k, v in beatmap.items()}
            for beatmap in response.json()
        )
        converted = (
            {
                k: self._beatmap_conversions[k](v)
                for k, v in d.items()
                if k in self._beatmap_conversions
            }
            for d in as_dicts
        )

        out = []
        for d in converted:
            beatmap_response = requests.get(
                self.api_url + f'/osu/{d.pop("beatmap_id")}',
            )
            beatmap_response.raise_for_status()
            out.append(BeatmapResult(
                Beatmap.parse(beatmap_response.text),
                **d,
            ))

        if beatmap_id is not None or beatmap_md5 is not None:
            out, = out

        return out
