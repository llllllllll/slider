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
