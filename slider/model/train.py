from sklearn.model_selection import train_test_split


from .features import extract_from_replay_directory
from .model import Model


def train_model(beatmap_features, accuracies, model=None):
    """Train a model on the given beatmap and the accuracy achieved on it.

    Parameters
    ----------
    beatmap_features : np.ndarray[float64]
        An array with one row per beatmap to train on where the columns are the
        features of the map.
    accuracies : np.ndarray[float64]
        An array with the same length as ``beatmap_features`` which is the
        actual accuracy achieved on the beatmap.
    model : OsuModel, optional
        The model to use.

    Returns
    -------
    model : Regressor
        The scikit-learn model fit with the input data. New observations can
        be added by re-fitting the new replays.
    """
    if model is None:
        model = Model()

    model.fit(beatmap_features, accuracies)
    return model


def train_from_replay_directory(path, library, age=None, model=None):
    """Train a model from a directory of replays.

    Parameters
    ----------
    path : str or pathlib.Path
        The path to the directory of ``.osr`` files.
    library : Library
        The beatmap library to use when parsing the replays.
    age : datetime.timedelta, optional
        Only count replays less than this age old.
    model : OsuModel, optional
        The model to use.

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
    return train_model(
        *extract_from_replay_directory(path, library, age=age),
        model=model,
    )


def test_model_from_replay_directory(path,
                                     library,
                                     age=None,
                                     model=None,
                                     test_size=None,
                                     train_size=None):
    """Train a model from a directory of replays.

    Parameters
    ----------
    path : str or pathlib.Path
        The path to the directory of ``.osr`` files.
    library : Library
        The beatmap library to use when parsing the replays.
    age : datetime.timedelta, optional
        Only count replays less than this age old.
    model : OsuModel, optional
        The model to use.
    test_size : float, optional
        The percent of data to use to test the model. The default is 0.25.
    train_size : float, optional
        The percent of data to use to train the model. The default is 0.75.

    Returns
    -------
    model : Regressor
        The scikit-learn model fit with the input data. New observations can
        be added by re-fitting the new replays.
    predictions : np.ndarray[float64]
        The predictions made for the test features.
    actual : np.ndarray[float64]
        The actual values for accuracies of the test label.

    Notes
    -----
    The same beatmap may appear more than once if there are multiple replays
    for this beatmap.
    """

    features, accuracy = extract_from_replay_directory(
        path,
        library,
        age=age,
    )
    train_features, test_features, train_acc, test_acc = train_test_split(
        features,
        accuracy,
        test_size=test_size,
        train_size=train_size,
    )

    m = train_model(train_features, train_acc, model=model)
    return m, m.predict(test_features), test_acc
