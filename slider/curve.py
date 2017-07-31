from abc import ABCMeta, abstractmethod
import math
import bisect

import numpy as np
from scipy.misc import comb
from itertools import accumulate

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
        cls._kind_dispatch
        for meth in super(cls, cls).__abstractmethods__:
            impl = getattr(cls, meth)
            if impl.__doc__ is None:
                impl.__doc__ = getattr(super(cls, cls), meth).__doc__

        for kind in cls.kinds:
            cls._kind_dispatch[kind] = cls


class Bezier(Curve):
    kinds = 'L'

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
        self._curves = [Bezier(points, None) for points in metapoints]

    @lazyval
    def _ts(self):
        lengths = [c.length for c in self._curves]
        length = sum(lengths)
        out = []
        for i, j in enumerate(accumulate(lengths[:-1])):
            self._curves[i].req_length = lengths[i]
            out.append(j / length)
        self._curves[-1].req_length = max(0, lengths[-1] - (length - self.req_length))
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


class Passthrough(Curve):
    kinds = 'P'

    def __init__(self, points, req_length):
        self.points = points
        self.req_length = req_length
        self._center = center = get_center(*self.points)

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

        length = abs(self._angle * math.sqrt(coordinates[0][0] ** 2 + coordinates[0][1] ** 2))
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


def get_center(p1, p2, p3):
    """Returns the Position of the center of the circle described by the 3
    points

    Parameters
    ----------
    p1, p2, p3 : Position
        The three positions.

    Returns
    -------
    center : Position
        The center of the three points.
    """
    if p2.x == p1.x:
        # normal t calc won't work
        t = (p3.y - p1.y) / (2 * (p3.x - p2.x))

        return Position(
            0.5 * (p2.x + p3.x) + t * (p3.y - p2.y),
            0.5 * (p2.y + p3.y) - t * (p3.x - p2.x),
        )
    elif p3.y == p2.y:
        t = (p3.x - p1.x) / (2 * (p2.y - p1.y))
    else:
        t = (
            (
                (-(p1.y - p3.y) / (2 * (p2.x - p1.x))) -
                (
                    ((p3.x - p2.x) * (p1.x - p3.x)) /
                    (2 * (p2.x - p1.x) * (p3.y - p2.y))
                )
            ) *
            (
                ((p2.x - p1.x) * (p3.y - p2.y)) /
                (
                    ((p3.x - p2.x) * (p2.y - p1.y)) -
                    ((p2.x - p1.x) * (p3.y - p2.y))
                )
            )
        )

    return Position(
        0.5 * (p1.x + p2.x) + t * (p2.y - p1.y),
        0.5 * (p1.y + p2.y) - t * (p2.x - p1.x),
    )


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
