Spearmint
=========

`Spearmint <https://github.com/llllllllll/Spearmint/tree/slider-fixes>`_ is a
bayesian optimizer for machine learning models.

.. note::

   Spearmint is not actively maintained, the link above is to a fork of
   spearmint with some fixes applied to work with slider. Be sure you are using
   the ``slider-fixes`` branch before running spearmint.

The files in this directory specify tasks and parameter spaces to search over to
attempt to minimize the error in the osu! model.

MLPRegressor All Solvers
------------------------

This experiment searches across options in the scikit-learn ``MLPRegressor``
model using only parameters that apply to all of the solvers.
