from collections import namedtuple
from datetime import datetime
import os

import numpy as np

from ..beatmap import Circle, Slider
from ..replay import Replay


# axis indices
_x = 0
_y = 1
_z = 2


def hit_object_coordinates(hit_objects):
    """Return the coordinates of the hit objects as a (3, len(hit_objects))
    array.

    Parameters
    ----------
    hit_objects : iterable[HitObject]
        The hit objects to take the coordinates of.

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

    return np.array([xs, ys, zs], dtype=np.float64)


# angle indices
pitch = 0
roll = 1
yaw = 2


def hit_object_angles(hit_objects):
    """Compute the angle from one hit object to the next in 3d space with time
    along the Z axis.

    Parameters
    ----------
    hit_objects : iterable[HitObject]
        The hit objects to compute the angles about.

    Returns
    -------
    angles : ndarray[float]
        An array shape (3, len(hit_objects) - 1) of pitch, roll, and yaw
        between each hit object. All angles are measured in radians.
    """
    coords = hit_object_coordinates(hit_objects)

    diff = np.diff(coords, axis=1)

    # (pitch, roll, yaw) x transitions
    out = np.empty((3, len(hit_objects) - 1), dtype=np.float64)
    np.arctan2(diff[_y], diff[_z], out=out[pitch])
    np.arctan2(diff[_y], diff[_x], out=out[roll])
    np.arctan2(diff[_z], diff[_x], out=out[yaw])

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


def extract_features(beatmap):
    """Extract all features from a beatmap.

    Parameters
    ----------
    beatmap : Beatmap
        The beatmap to extract features from.

    Returns
    -------
    features : dict[str, np.float64]
        The features by name.
    """
    # ignore the direction of the angle, just take the magnitude
    angles = np.abs(hit_object_angles(beatmap.hit_objects_no_spinners))
    mean_angles = np.mean(angles, axis=1)
    median_angles = np.median(angles, axis=1)
    max_angles = np.max(angles, axis=1)

    circles, sliders, spinners = count_hit_objects(beatmap.hit_objects)

    return {
        'HP': beatmap.hp,
        'CS': beatmap.cs,
        'OD': beatmap.od,
        'AR': beatmap.ar,

        'bpm-min': beatmap.bpm_min,
        'bpm-max': beatmap.bpm_max,

        'circle-count': circles,
        'slider-count': sliders,
        'spinner-count': spinners,

        'slider-multiplier': beatmap.slider_multiplier,
        'slider-tick-rate': beatmap.slider_tick_rate,

        'mean-pitch': mean_angles[pitch],
        'mean-roll': mean_angles[roll],
        'mean-yaw': mean_angles[yaw],
        'median-pitch': median_angles[pitch],
        'median-roll': median_angles[roll],
        'median-yaw': median_angles[yaw],
        'max-pitch': max_angles[pitch],
        'max-roll': max_angles[roll],
        'max-yaw': max_angles[yaw],
    }


def _fst(tup):
    return tup[0]


def extract_feature_array(beatmaps):
    """Extract all features from a beatmap.

    Parameters
    ----------
    beatmap : Beatmap
        The beatmap to extract features from.

    Returns
    -------
    features : np.ndarray[float64]
        The features as an array.
    """
    return np.array(
        [
            [
                snd for
                fst, snd in sorted(extract_features(beatmap).items(), key=_fst)
            ]
            for beatmap in beatmaps
            if len(beatmap.hit_objects) >= 2
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
    beatmaps = []
    accuracies = []

    beatmap_append = beatmaps.append
    accuracy_append = accuracies.append

    for entry in os.scandir(path):
        if not entry.name.endswith('.osr'):
            continue

        replay = Replay.from_path(entry, library=library)
        if age is not None and datetime.utcnow() - replay.timestamp > age:
            continue

        beatmap_append(replay.beatmap)
        accuracy_append(replay.accuracy)

    return extract_feature_array(beatmaps), np.array(accuracies)
