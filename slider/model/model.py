import numpy as np
from sklearn.neural_network import MLPRegressor as _MLPRegressor

from .features import extract_feature_array


class OsuModel:
    """Base mixin for sklearn models to clip the results and add a
    ``predict_beatmap`` method.
    """
    def predict(self, *args, **kwargs):
        return np.clip(super().predict(*args, **kwargs), 0, 1)

    def predict_beatmap(self, beatmap, **kwargs):
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
        return self.predict(extract_feature_array([(beatmap, kwargs)]))[0]


class MLPRegressor(OsuModel, _MLPRegressor):
    """An osu! aware MLPRegressor.
    """
    def __init_(hidden_layer_sizes=(100, 50),
                solver='lbfgs',
                activation='tanh',
                tol=1e-9,
                warm_start=True,
                **kwargs):
        super().__init__(
            hidden_layer_sizes=hidden_layer_sizes,
            solver=solver,
            activation=activation,
            tol=tol,
            warm_start=warm_start,
            **kwargs,
        )


# The default model
Model = MLPRegressor
