from collections import namedtuple
from datetime import datetime
from enum import unique, IntEnum
import os

import numpy as np

from ..beatmap import Circle, Slider
from ..mod import ar_to_ms, ms_to_ar
from ..replay import Replay


@unique
class Axis(IntEnum):
    """Axis indices.
    """
    x = 0
    y = 1
    z = 2


def hit_object_coordinates(hit_objects, *, double_time=False, half_time=False):
    """Return the coordinates of the hit objects as a (3, len(hit_objects))
    array.

    Parameters
    ----------
    hit_objects : iterable[HitObject]
        The hit objects to take the coordinates of.
    double_time : bool, optional
        Apply double time compression to the Z axis.
    half_time : bool, optional
        Apply half time expansion to the Z axis.

    Returns
    -------
    coordinates : np.ndarray[float64]
        A shape (3, len(hit_objects)) array where the rows are the x, y, z
        coordinates of the nth hit object.

    Notes
    -----
    The z coordinate is reported in microseconds to make the angles more
    reasonable.
    """
    xs = []
    ys = []
    zs = []

    x = xs.append
    y = ys.append
    z = zs.append

    for hit_object in hit_objects:
        position = hit_object.position

        x(position.x)
        y(position.y)
        z(hit_object.time.total_seconds() * 100)

    coords = np.array([xs, ys, zs], dtype=np.float64)

    if double_time:
        coords[Axis.z] *= 4 / 3
    elif half_time:
        coords[Axis.z] *= 2 / 3

    return coords


class Angle(IntEnum):
    """Angle indices.
    """
    pitch = 0
    roll = 1
    yaw = 2


def hit_object_angles(hit_objects, *, double_time=False, half_time=False):
    """Compute the angle from one hit object to the next in 3d space with time
    along the Z axis.

    Parameters
    ----------
    hit_objects : iterable[HitObject]
        The hit objects to compute the angles about.
    double_time : bool, optional
        Apply double time compression to the Z axis.
    half_time : bool, optional
        Apply half time expansion to the Z axis.

    Returns
    -------
    angles : ndarray[float]
        An array shape (3, len(hit_objects) - 1) of pitch, roll, and yaw
        between each hit object. All angles are measured in radians.
    """
    coords = hit_object_coordinates(
        hit_objects,
        double_time=double_time,
        half_time=half_time,
    )
    diff = np.diff(coords, axis=1)

    # (pitch, roll, yaw) x transitions
    out = np.empty((3, len(hit_objects) - 1), dtype=np.float64)
    np.arctan2(diff[Axis.y], diff[Axis.z], out=out[Angle.pitch])
    np.arctan2(diff[Axis.y], diff[Axis.x], out=out[Angle.roll])
    np.arctan2(diff[Axis.z], diff[Axis.x], out=out[Angle.yaw])

    return out


hit_object_count = namedtuple('hit_object_count', 'circles sliders spinners')


def count_hit_objects(hit_objects):
    """Count the different hit element types.

    Parameters
    ----------
    hit_objects : hit_objects
        The hit objects to count the types of.

    Returns
    -------
    circles : int
        The count of circles.
    sliders : int
        The count of sliders.
    spinners : int
        The count of spinners.
    """
    circles = 0
    sliders = 0
    spinners = 0

    for hit_object in hit_objects:
        if isinstance(hit_object, Circle):
            circles += 1
        elif isinstance(hit_object, Slider):
            sliders += 1
        else:
            spinners += 1

    return hit_object_count(circles, sliders, spinners)


def extract_features(beatmap,
                     *,
                     easy=False,
                     hidden=False,
                     hard_rock=False,
                     double_time=False,
                     relax=False,
                     half_time=False,
                     flashlight=False):
    """Extract all features from a beatmap.

    Parameters
    ----------
    beatmap : Beatmap
        The beatmap to extract features from.
    easy : bool, optional
        Was the easy mod used?
    hidden : bool, optional
        Was the hidden mod used?
    hard_rock : bool, optional
        Was the hard rock mod used?
    double_time : bool, optional
        Was the double time mod used?
    hard : bool, optional
        Was the half time mod used?
    flashlight : bool, optional
        Was the flashlight mod used?

    Returns
    -------
    features : dict[str, np.float64]
        The features by name.
    """
    # ignore the direction of the angle, just take the magnitude
    angles = np.abs(hit_object_angles(
        beatmap.hit_objects_no_spinners,
        half_time=half_time,
        double_time=double_time,
    ))
    mean_angles = np.mean(angles, axis=1)
    median_angles = np.median(angles, axis=1)
    max_angles = np.max(angles, axis=1)

    circles, sliders, spinners = count_hit_objects(beatmap.hit_objects)

    pp_95, pp_96, pp_97, pp_98, pp_99, pp_100 = beatmap.performance_points(
        accuracy=[0.95, 0.96, 0.97, 0.98, 0.99, 1.00],
        easy=easy,
        hard_rock=hard_rock,
        half_time=half_time,
        double_time=double_time,
        hidden=hidden,
        flashlight=flashlight,
    )

    return {
        # basic stats
        'OD': beatmap.od(easy=easy, hard_rock=hard_rock),
        'CS': beatmap.cs(easy=easy, hard_rock=hard_rock),
        'AR': beatmap.ar(
            easy=easy,
            hard_rock=hard_rock,
            half_time=half_time,
            double_time=double_time,
        ),

        # mods
        'easy': float(easy),
        'hidden': float(hidden),
        'hard_rock': float(hard_rock),
        'double_time': float(double_time),
        'half_time': float(half_time),
        'flashlight': float(flashlight),

        # bpm
        'bpm-min': beatmap.bpm_min(
            half_time=half_time,
            double_time=double_time,
        ),
        'bpm-max': beatmap.bpm_max(
            half_time=half_time,
            double_time=double_time,
        ),

        # hit objects
        'circle-count': circles,
        'slider-count': sliders,
        'spinner-count': spinners,

        # hit object angles
        'mean-pitch': mean_angles[Angle.pitch],
        'mean-roll': mean_angles[Angle.roll],
        'mean-yaw': mean_angles[Angle.yaw],
        'median-pitch': median_angles[Angle.pitch],
        'median-roll': median_angles[Angle.roll],
        'median-yaw': median_angles[Angle.yaw],
        'max-pitch': max_angles[Angle.pitch],
        'max-roll': max_angles[Angle.roll],
        'max-yaw': max_angles[Angle.yaw],

        # stars
        'speed-stars': beatmap.speed_stars(
            easy=easy,
            hard_rock=hard_rock,
            half_time=half_time,
            double_time=double_time,
        ),
        'aim-stars': beatmap.aim_stars(
            easy=easy,
            hard_rock=hard_rock,
            half_time=half_time,
            double_time=double_time,
        ),
        'rhythm-awkwardness': beatmap.rhythm_awkwardness(
            easy=easy,
            hard_rock=hard_rock,
            half_time=half_time,
            double_time=double_time,
        ),

        # pp
        'PP-95%': pp_95,
        'PP-96%': pp_96,
        'PP-97%': pp_97,
        'PP-98%': pp_98,
        'PP-99%': pp_99,
        'PP-100%': pp_100,

    }


def _fst(tup):
    return tup[0]


def extract_feature_array(beatmaps_and_mods):
    """Extract all features from a beatmap.

    Parameters
    ----------
    beatmaps_and_mods : list[Beatmap, dict[str, bool]]
        The beatmaps and mod information to extract features from.

    Returns
    -------
    features : np.ndarray[float64]
        The features as an array.
    """
    return np.array(
        [
            [
                snd for
                fst, snd in sorted(
                    extract_features(beatmap, **mods).items(),
                    key=_fst,
                )
            ]
            for beatmap, mods in beatmaps_and_mods
        ]
    )


def extract_from_replay_directory(path, library, age=None):
    """Extract a labeled feature set from a path to directory of replays.

    Parameters
    ----------
    path : str or pathlib.Path
        The path to the directory of ``.osr`` files.
    library : Library
        The beatmap library to use when parsing the replays.
    age : datetime.timedelta, optional
        Only count replays less than this age old.

    Returns
    -------
    features : np.ndarray[float]
        The array of input data with one row per play.
    accuracies : np.ndarray[float]
        The array of accuracies achieved on each of the beatmaps in
        ``features``.

    Notes
    -----
    The same beatmap may appear more than once if there are multiple replays
    for this beatmap.
    """
    beatmaps_and_mods = []
    accuracies = []

    beatmap_and_mod_append = beatmaps_and_mods.append
    accuracy_append = accuracies.append

    for entry in os.scandir(path):
        if not entry.name.endswith('.osr'):
            continue

        replay = Replay.from_path(entry, library=library)
        if age is not None and datetime.utcnow() - replay.timestamp > age:
            continue

        if (replay.autoplay or
                replay.spun_out or
                replay.auto_pilot or
                replay.cinema or
                replay.relax):
            # ignore plays with mods that are not representative of user skill
            continue

        if len(replay.beatmap.hit_objects) < 2:
            continue

        beatmap_and_mod_append((
            replay.beatmap, {
                'easy': replay.easy,
                'hidden': replay.hidden,
                'hard_rock': replay.hard_rock,
                'double_time': replay.double_time,
                'half_time': replay.half_time,
                'flashlight': replay.flashlight,
            },
        ))
        accuracy_append(replay.accuracy)

    fs = extract_feature_array(beatmaps_and_mods)
    mask = np.isfinite(fs).all(axis=1)
    return fs[mask], np.array(accuracies)[mask]
