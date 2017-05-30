"""Shims for when numpy is not installed.
"""
from itertools import compress, repeat
import math
import operator as op

__all__ = [
    'array',
    'full_like',
    'minimum',
    'maximum',
    'floor',
    'ceil',
    'round',
    'sqrt',
    'log2',
    'log10',
    'asscalar',
    'shape',
]

binops = frozenset({
    op.add,
    op.sub,
    op.mul,
    op.truediv,
    op.floordiv,
    op.mod,
    pow,
    op.and_,
    op.or_,
    op.xor,
    op.lt,
    op.le,
    op.eq,
    op.ne,
    op.ge,
    op.gt,
})


def invert(element):
    if isinstance(element, bool):
        return not element

    return ~element


unops = frozenset({
    op.neg,
    invert,
})


def bad_broadcast(lhs, rhs):
    return ValueError(
        'operands could not be broadcast together with'
        f' shapes ({len(lhs)},) ({len(rhs)},)',
    )


def broadcast(lhs, rhs):
    """Broadcast two ElementWise objects into the same shape if possible.

    Parameters
    ----------
    lhs, rhs : ElementWise or scalar
        The objects to broadcast together.

    Returns
    -------
    lhs, rhs : ElementWise
        The broadcasted operands.

    Raises
    -------
    ValueError
        Raised when the operands cannot be broadcasted together.
    """
    if not isinstance(lhs, ElementWise):
        lhs = ElementWise([lhs])
    if not isinstance(rhs, ElementWise):
        rhs = ElementWise([rhs])

    if len(lhs) == len(rhs):
        return lhs, rhs

    if len(lhs) == 1:
        return ElementWise([lhs._elements[0]] * len(rhs)), rhs

    if len(rhs) == 1:
        return lhs, ElementWise([rhs._elements[0]] * len(lhs))

    raise bad_broadcast(lhs, rhs)


def _binop(operator, doc=None):
    """Create an elementwise operator.

    Parameters
    ----------
    operator : callable
        The scalar operator.
    doc : str, optional
        The docstring.

    Returns
    -------
    op : callable
        The elementwise operator.
    """
    def op(self, other):
        if (not isinstance(self, ElementWise) and
                not isinstance(other, ElementWise)):
                return operator(self, other)

        return ElementWise(list(map(operator, *broadcast(self, other))))
    op.__doc__ = doc
    return op


def _rbinop(operator, doc=None):
    """Create a reflected elementwise operator.

    Parameters
    ----------
    operator : callable
        The scalar operator.
    doc : str, optional
        The docstring.

    Returns
    -------
    op : callable
        The elementwise operator.
    """
    def op(self, other):
        return ElementWise(list(map(operator, *broadcast(other, self))))

    op.__doc__ = doc
    return op


def _unop(operator, doc=None):
    """Create an elementwise operator.

    Parameters
    ----------
    operator : callable
        The scalar operator.
    doc : str, optional
        The docstring.

    Returns
    -------
    op : callable
        The elementwise operator.
    """
    def op(self):
        if not isinstance(self, ElementWise):
            return operator(self)

        return ElementWise(list(map(operator, self)))

    op.__doc__ = doc
    return op


class ElementWise:
    """An object which does elementwise arithmetic

    Parameters
    ----------
    elements : list[any]
        The objects to broadcast arithmetic to.

    See Also
    --------
    :func:`slider.element_wise.array`
    """
    def __init__(self, elements):
        self._elements = elements

    ns = locals()
    for o in binops:
        ns[f'__{o.__name__}__'] = _binop(o)
        ns[f'__r{o.__name__}__'] = _rbinop(o)

    for o in unops:
        ns[f'__{o.__name__}__'] = _unop(o)

    del o
    del ns

    def __iter__(self):
        return iter(self._elements)

    def __len__(self):
        return len(self._elements)

    @property
    def shape(self):
        return (len(self),)

    def __getitem__(self, ix):
        elements = self._elements
        try:
            return elements[ix]
        except TypeError:
            pass

        if isinstance(ix[0], bool):
            if len(self) != len(ix):
                raise bad_broadcast(self, ix)
            return ElementWise(list(compress(elements, ix)))

        return ElementWise([elements[i] for i in ix])

    def __setitem__(self, ix, value):
        elements = self._elements
        try:
            elements[ix] = value
            return
        except TypeError:
            pass

        if isinstance(ix[0], bool):
            if len(self) != len(ix):
                raise bad_broadcast(self, ix)

            try:
                values = iter(value)
            except TypeError:
                values = repeat(value)
            for n, mask in enumerate(ix):
                if mask:
                    elements[n] = next(values)
        else:
            try:
                it = iter(value)
            except TypeError:
                it = repeat(value)

            for n, v in zip(ix, it):
                elements[n] = v

    def __repr__(self):
        return f'<ElementWise: {self._elements}>'


def array(elements, **kwargs):
    """Stub for ``np.array`` which returns an ``ElementWise`` instead of
    an ``ndarray``.

    Parameters
    ----------
    elements : any
        The elements of the elementwise
    **kwargs
        Ignored.

    Returns
    -------
    elemwise : ElementWise
        An ElementWise that wraps the given elements.
    """
    try:
        elements = list(elements)
    except TypeError:
        elements = [elements]

    return ElementWise(elements)


def full_like(elemwise, value):
    """Create a new ``Elemwise`` with the same length as another.

    Parameters
    ----------
    elemwise : ElementWise
        The elementwise to take the shape from.
    value : any
        The value to populate the elementwise with.

    Returns
    -------
    full : ElementWise
        The new elementwise with the given value.
    """
    return ElementWise([value] * len(elemwise))


minimum = _binop(
    min,
    """Elementwise minimum.

    Parameters
    ----------
    lhs, rhs : elemwise-like
        The elemwise or scalar values to take the minimum of.

    Returns
    -------
    min : ElementWise
        The element wise minimum.
    """,
)

maximum = _binop(
    max,
    """Elementwise maximum.

    Parameters
    ----------
    lhs, rhs : elemwise-like
        The elemwise or scalar values to take the maximum of.

    Returns
    -------
    max : ElementWise
        The element wise maximum.
    """,
)

floor = _unop(
    math.floor,
    """Elementwise floor function.

    Parameters
    ----------
    elemwise : ElementWise
        The values to floor.

    Returns
    -------
    floored : ElementWise
        The floored values.
    """,
)

ceil = _unop(
    math.ceil,
    """Elementwise ceil function.

    Parameters
    ----------
    elemwise : ElementWise
        The values to ceil.

    Returns
    -------
    ceiled : ElementWise
        The ceiled values.
    """,
)

round = _unop(
    round,
    """Elementwise round function.

    Parameters
    ----------
    elemwise : ElementWise
        The values to round.

    Returns
    -------
    rounded : ElementWise
        The rounded values.
    """,
)

sqrt = _unop(
    math.sqrt,
    """Elementwise sqrt function.

    Parameters
    ----------
    elemwise : ElementWise
        The values to take the square root of.

    Returns
    -------
    sqrts : ElementWise
        The square roots.
    """,
)

log2 = _unop(
    math.log2,
    """Elementwise log2 function.

    Parameters
    ----------
    elemwise : ElementWise
        The values to take log2.

    Returns
    -------
    log2s : ElementWise
        The log2 values.
    """,
)

log10 = _unop(
    math.log10,
    """Elementwise log10 function.

    Parameters
    ----------
    elemwise : ElementWise
        The values to take log10.

    Returns
    -------
    log10s : ElementWise
        The log10 values.
    """,
)


def asscalar(elemwise):
    """Convert a length-1 elemwise into a scalar.

    Parameters
    ----------
    elemwise : ElementWise
        The length-1 elemwise to get the scalar value of.

    Returns
    -------
    scalar : any
        The scalar value.
    """
    elem, = elemwise
    return elem


def shape(ob):
    """The shape of an object.

    Parameters
    ----------
    ob : any
        The object to take the shape of.

    Returns
    -------
    shape : tuple
        The shape.
    """
    if isinstance(ob, (list, ElementWise)):
        return (len(ob),)

    return ()
