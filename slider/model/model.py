from itertools import chain

import numpy as np
from sklearn.neural_network import MLPRegressor as _MLPRegressor
from sklearn.preprocessing import StandardScaler

from .features import extract_feature_array


class OsuModel:
    """Base mixin for sklearn models to clip the results and add a
    ``predict_beatmap`` method.
    """
    def predict(self, *args, **kwargs):
        return np.clip(super().predict(*args, **kwargs), 0, 1)

    def predict_beatmap(self, beatmap, *mods, **kwargs):
        """Predict the user's score for the given beatmap.

        Parameters
        ----------
        beatmap : Beatmap
            The map to predict the performance of.
        **kwargs
            The mods used.

        Returns
        -------
        accuracy : float
            The user's expected accuracy in the range [0, 1].
        """
        return self.predict(extract_feature_array([
            (beatmap, mod)
            for mod in chain(mods, [kwargs])
        ]))


class MLPRegressor(OsuModel, _MLPRegressor):
    """An osu! aware MLPRegressor.
    """
    def __init__(self,
                 alpha=0.009,
                 solver='lbfgs',
                 activation='tanh',
                 hidden_layer_sizes=(54, 199, 66),
                 max_iter=1000,
                 tol=1e-9,
                 warm_start=True,
                 **kwargs):
        super().__init__(
            alpha=alpha,
            solver=solver,
            activation=activation,
            hidden_layer_sizes=hidden_layer_sizes,
            tol=tol,
            warm_start=warm_start,
            **kwargs,
        )
        self._normalize = StandardScaler()

    def fit(self, train, labels):
        train = self._normalize.fit_transform(train, labels)
        return super().fit(train, labels)

    def predict(self, features):
        return super().predict(self._normalize.transform(features))


# The default model
Model = MLPRegressor
