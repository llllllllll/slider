"""Host a server to hold the local library and replay data in memory.

Reading the LocalLibrary and replay data dominates the runtime of the task so
this dramatically speeds up the hyperparameter optimization.

"""
from datetime import timedelta

import flask
import numpy as np
from sklearn.model_selection import train_test_split

from slider import LocalLibrary
from slider.model import train_model, extract_from_replay_directory
from slider.model.model import MLPRegressor


features, accuracy = extract_from_replay_directory(
    '../data/replays',
    LocalLibrary('../data/maps'),
    age=timedelta(days=365 // 2),
)


app = flask.Flask(__name__)


@app.route('/train')
def train():
    train_labels, test_labels, train_acc, test_acc = train_test_split(
        features,
        accuracy,
    )

    def model():
        return MLPRegressor(
            alpha=float(flask.request.args['alpha']),
            hidden_layer_sizes=list(map(
                int,
                flask.request.args.getlist('hidden_layer_sizes'),
            )),
            solver=flask.request.args['solver'],
            activation=flask.request.args['activation'],
        )

    m = train_model(train_labels, train_acc, model=model)
    return str(np.mean(np.abs(test_acc - m.predict(test_labels))))
