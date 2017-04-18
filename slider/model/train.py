from .features import extract_from_replay_directory
from .model import Regressor


def train_model(beatmap_features, accuracies):
    """Train a model on the given beatmap and the accuracy achieved on it.

    Parameters
    ----------
    beatmap_features : np.ndarray[float64]
        An array with one row per beatmap to train on where the columns are the
        features of the map.
    accuracies : np.ndarray[float64]
        An array with the same length as ``beatmap_features`` which is the
        actual accuracy achieved on the beatmap.

    Returns
    -------
    model : Regressor
        The scikit-learn model fit with the input data. New observations can
        be added by re-fitting the new replays.
    """
    model = Regressor(
        hidden_layer_sizes=(100, 50),
        solver='lbfgs',
        activation='tanh',
        tol=1e-9,
        warm_start=True,
    )
    model.fit(beatmap_features, accuracies)
    return model


def train_from_replay_directory(path, library, age=None):
    """Train a model from a directory of replays.

    Parameters
    ----------
    path : str or pathlib.Path
        The path to the directory of ``.osr`` files.
    library : Library
        The beatmap library to use when parsing the replays.
    age : datetime.timedelta, optional
        Only count replays less than this age old.

    Returns
    -------
    model : Regressor
        The scikit-learn model fit with the input data. New observations can
        be added by re-fitting the new replays.

    Notes
    -----
    The same beatmap may appear more than once if there are multiple replays
    for this beatmap.
    """
    return train_model(*extract_from_replay_directory(path, library, age=age))
