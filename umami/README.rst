Umami
=====

`Umami <https://github.com/llllllllll/umami>`_ is a bayesian optimizer for
machine learning models.

.. note::

   Umami is a fork of `Spearmint <https://github.com/JasperSnoek/spearmint>`_
   which was made to get the GPL version of Spearmint working to optimize
   Slider's osu! models.

The files in this directory specify tasks and parameter spaces to search over to
attempt to minimize the error in the osu! model.

MLPRegressor All Solvers
------------------------

This experiment searches across options in the scikit-learn ``MLPRegressor``
model using only parameters that apply to all of the solvers.
