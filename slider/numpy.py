import os

try:
    if os.environ['SLIDER_NO_NUMPY']:
        raise ImportError('use element_wise impl')

    from numpy import *
    from numpy import round

    def finalize(array):
        return array

except ImportError:
    from .element_wise import *

    def finalize(array):
        return array._elements
