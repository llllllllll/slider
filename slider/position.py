from collections import namedtuple
import numpy as np


class Position(namedtuple('Position', 'x y')):
    """A position on the osu! screen.

    Parameters
    ----------
    x : int or float
        The x coordinate in the range.
    y : int or float
        The y coordinate in the range.

    Notes
    -----
    The visible region of the osu! standard playfield is [0, 512] by [0, 384].
    Positions may fall outside of this range for slider curve control points.
    """
    x_max = 512
    y_max = 384

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def int_equal(self, other):
        """Checks if coordinates of two Positions are the same after being cast to int.

        Parameters
        ----------
        other : Position
            The Position to be compared with.

        Returns
        -------
        equal : bool
            If two Positions are equal.
        """
        return int(self.x) == int(other.x) and int(self.y) == int(other.y)


class Point(namedtuple('Point', 'x y offset')):
    """A position and time on the osu! screen.

    Parameters
    ----------
    x : int or float
        The x coordinate in the range.
    y : int or float
        The y coordinate in the range.
    offset : timedelta
        The time

    Notes
    -----
    The visible region of the osu! standard playfield is [0, 512] by [0, 384].
    Positions may fall outside of this range for slider curve control points.
    """


def distance(start, end):
    return np.sqrt((start.x - end.x) ** 2 + (start.y - end.y) ** 2)
