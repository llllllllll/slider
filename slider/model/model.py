import numpy as np
from sklearn.neural_network import MLPRegressor

from .features import extract_feature_array


class Regressor(MLPRegressor):
    """A regressor with osu! beatmap specific helpers.
    """
    def predict(*args, **kwargs):
        return np.clip(super().predict(*args, **kwargs), 0, 1)

    def predict_beatmap(self, beatmap):
        """Predict the user's score for the given beatmap.

        Parameters
        ----------
        beatmap : Beatmap
            The map to predict the performance of.

        Returns
        -------
        accuracy : float
            The user's expected accuracy in the range [0, 1].
        """
        return self.predict_beatmap(extract_feature_array([beatmap]))
