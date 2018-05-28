from collections import namedtuple


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

    def __repr__(self):
        return (
            f'<{type(self).__qualname__}: ({self.x}, {self.y})>'
        )

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __hash__(self):
        return hash((self.x, self.y))


class Point(namedtuple('Point', 'x y offset')):
    """A position and time on the osu! screen.

    Parameters
    ----------
    x : int or float
        The x coordinate in the range.
    y : int or float
        The y coordinate in the range.
    offset : int or float
        The time

    Notes
    -----
    The visible region of the osu! standard playfield is [0, 512] by [0, 384].
    Positions may fall outside of this range for slider curve control points.
    """

    def __repr__(self):
        return (
            f'<{type(self).__qualname__}: ({self.x}, {self.y}), {self.offset.total_seconds() * 1000:g}ms>'
        )
