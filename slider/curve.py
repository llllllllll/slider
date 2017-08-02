import bisect
import math
from itertools import accumulate

import numpy as np
from scipy.misc import comb
from toolz import sliding_window

from .abc import ABCMeta, abstractmethod
from .position import Position
from .utils import lazyval


class Curve(metaclass=ABCMeta):
    _kind_dispatch = {}

    @classmethod
    def from_kind_and_points(cls, kind, points, req_length):
        try:
            subcls = cls._kind_dispatch[kind]
        except KeyError:
            raise ValueError(f'unknown curve type: {kind!r}')

        return subcls(points, req_length)

    @abstractmethod
    def __call__(self, t):
        """Compute the position of the curve at time ``t``.

        Parameters
        ----------
        t : float
            The time along the distance of the curve in the range [0, 1]

        Returns
        -------
        position : Position
            The position of the curve.
        """
        raise NotImplementedError('__call__')

    def __init_subclass__(cls):
        for kind in cls.kinds:
            cls._kind_dispatch[kind] = cls


class Bezier(Curve):
    kinds = ()

    def __init__(self, points, req_length):
        self.points = points
        self._coordinates = np.array(points).T
        self.req_length = req_length

    def __call__(self, t):
        return self.at(t * (self.req_length / self.length))

    def at(self, t):
        points = self.points

        n = len(points) - 1
        ixs = np.arange(n + 1)
        x, y = np.sum(
            comb(n, ixs) *
            (1 - t) ** (n - ixs) *
            t ** ixs *
            self._coordinates,
            axis=1,
        )
        return Position(x, y)

    @lazyval
    def length(self):
        """Approximates length as piecewise linear"""
        total = 0
        # todo: choose number of points to reduce error below a bound
        points = [self.at(t) for t in np.linspace(0, 1, num=5)]
        for i in range(len(points) - 1):
            dx = points[i + 1].x - points[i].x
            dy = points[i + 1].y - points[i].y
            total += math.sqrt(dx ** 2 + dy ** 2)
        return total


class MetaCurve(Curve):
    kinds = 'B'

    def __init__(self, points, req_length):
        metapoints = split_at_dupes(points)
        self.points = points
        self.req_length = req_length
        self._curves = [Bezier(subpoints, None) for subpoints in metapoints]

    @lazyval
    def _ts(self):
        lengths = [c.length for c in self._curves]
        length = sum(lengths)
        out = []
        for i, j in enumerate(accumulate(lengths[:-1])):
            self._curves[i].req_length = lengths[i]
            out.append(j / length)
        self._curves[-1].req_length = max(
            0,
            lengths[-1] - (length - self.req_length),
        )
        out.append(1)
        return out

    def __call__(self, t):
        ts = self._ts
        if len(self._curves) == 1:
            # Special case where we only have one curve
            return self._curves[0](t)

        bi = bisect.bisect_left(ts, t)
        if bi == 0:
            pre_t = 0
        else:
            pre_t = ts[bi - 1]

        post_t = ts[bi]

        return self._curves[bi]((t - pre_t) / (post_t - pre_t))


class LinearMetaCurve(MetaCurve):
    kinds = 'L'

    def __init__(self, points, req_length):
        self.points = points
        self.req_length = req_length
        self._curves = [
            Bezier(subpoints, None) for subpoints in sliding_window(2, points)
        ]


class Perfect(Curve):
    kinds = 'P'

    def __new__(cls, points, req_length):
        if len(points) != 3:
            # it seems osu! uses the bezier curve if there are more than 3
            # points
            # https://github.com/ppy/osu/blob/7fbbe74b65e7e399072c198604e9db09fb729626/osu.Game/Rulesets/Objects/SliderCurve.cs#L32  # noqa
            return Bezier(points, req_length)

        try:
            center = get_center(*points)
        except ValueError:
            # we cannot use a perfect curve function for collinear points;
            # osu! also falls back to a bezier here
            return Bezier(points, req_length)

        self = super().__new__(cls)
        self._init(points, req_length, center)
        return self

    def _init(self, points, req_length, center):
        self.points = points
        self.req_length = req_length
        self._center = center

        coordinates = np.array(points) - center

        # angles of 3 points to center
        start_angle, end_angle = np.arctan2(
            coordinates[::2, 1],
            coordinates[::2, 0],
        )

        # normalize so that self._angle is positive
        if end_angle < start_angle:
            end_angle += 2 * math.pi

        # angle of arc sector that describes slider
        self._angle = end_angle - start_angle

        # switch angle direction if necessary
        a_to_c = coordinates[2] - coordinates[0]
        ortho_a_to_c = np.array((a_to_c[1], -a_to_c[0]))
        if np.dot(ortho_a_to_c, coordinates[1] - coordinates[0]) < 0:
            self._angle = -(2 * math.pi - self._angle)

        length = abs(
            self._angle *
            math.sqrt(coordinates[0][0] ** 2 + coordinates[0][1] ** 2),
        )
        if length > req_length:
            self._angle *= req_length / length

    def __call__(self, t):
        return rotate(self.points[0], self._center, self._angle * t)


class Catmull(Curve):
    kinds = 'C'

    def __init__(self, points, req_length):
        self.points = points
        self.req_length = req_length

    def __call__(self, t):
        raise NotImplementedError('catmull positions not supported yet')


def get_center(a, b, c):
    """Returns the Position of the center of the circle described by the 3
    points

    Parameters
    ----------
    a, b, c : Position
        The three positions.

    Returns
    -------
    center : Position
        The center of the three points.

    Notes
    -----
    This uses the same algorithm as osu!
    https://github.com/ppy/osu/blob/7fbbe74b65e7e399072c198604e9db09fb729626/osu.Game/Rulesets/Objects/CircularArcApproximator.cs#L23  # noqa
    """
    a, b, c = np.array([a, b, c])

    a_squared = np.sum(np.square(b - c))
    b_squared = np.sum(np.square(a - c))
    c_squared = np.sum(np.square(a - b))

    if np.isclose([a_squared, b_squared, c_squared], 0).any():
        raise ValueError()

    s = a_squared * (b_squared + c_squared - a_squared)
    t = b_squared * (a_squared + c_squared - b_squared)
    u = c_squared * (a_squared + b_squared - c_squared)

    sum_ = s + t + u

    if np.isclose(sum_, 0):
        raise ValueError()

    return Position(*(s * a + t * b + u * c) / sum_)


def rotate(position, center, radians):
    """Returns a Position rotated r radians around centre c from p
    Parameters
    ----------
    position : Position
        The position to rotate.
    center : Position
        The point to rotate about.
    radians : float
        The number of radians to rotate ``position`` by.
    """
    p_x, p_y = position
    c_x, c_y = center

    x_dist = p_x - c_x
    y_dist = p_y - c_y

    return Position(
        (x_dist * math.cos(radians) - y_dist * math.sin(radians)) + c_x,
        (x_dist * math.sin(radians) + y_dist * math.cos(radians)) + c_y,
    )


def split_at_dupes(inp):
    out = []
    oldi = 0
    for i in range(1, len(inp)):
        if inp[i] == inp[i - 1]:
            out.append(inp[oldi:i])
            oldi = i
    out.append(inp[oldi:])
    return out
