from collections import namedtuple
from datetime import timedelta
from typing import NamedTuple, Any


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


class Tick(NamedTuple):
    """A position and time on the osu! screen, for use with ``Slider``s

    Parameters
    ----------
    position : Position
        The Position of the tick.
    time : timedelta
        The time of the tick.
    parent : Any
        The parent object of the tick
    is_note : bool = False
        Whether the tick is considered a note in osu!catch or not
    """
    position: Position
    time: timedelta
    parent: Any
    is_note: bool = False

    def __repr__(self):
        return (
            f'<{type(self).__qualname__}{" note" if self.is_note else ""}: '
            f'{self.position}, '
            f'{self.time.total_seconds() * 1000:g}ms>'
        )

    # parent not used due to Slider having no __eq__ and __hash__
    # a tick cannot be in the same position and time anyway
    def __eq__(self, other):
        return (
            self.position == other.position 
            and self.time == other.time
            and self.is_note == other.is_note
        )

    def __hash__(self):
        return hash((self.position, self.time, self.is_note))
