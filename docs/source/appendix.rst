Appendix
========

Beatmap
-------

.. autoclass:: slider.beatmap.Beatmap
   :members:

.. autoclass:: slider.beatmap.HitObject
   :members:

.. autoclass:: slider.beatmap.Circle
   :members:

.. autoclass:: slider.beatmap.Slider
   :members:

.. autoclass:: slider.beatmap.Spinner
   :members:

.. autoclass:: slider.beatmap.HoldNote
   :members:

Client
------

.. autoclass:: slider.client.Client
   :members:

Library
-------

.. autoclass:: slider.library.Library
   :members:

.. autoclass:: slider.library.LocalLibrary
   :members:

.. autoclass:: slider.library.ClientLibrary
   :members:

.. autoclass:: slider.library.ChainedLibrary
   :members:

Replay
------

.. autoclass:: slider.replay.Replay
   :members:

Game Modes
----------

.. autoclass:: slider.game_mode.GameMode
   :undoc-members:


Mods
----

.. autoclass:: slider.mod.Mod
   :undoc-members:

.. autofunction:: slider.mod.ar_to_ms

.. autofunction:: slider.mod.ms_to_ar

Utilities
---------

.. autoclass:: slider.position.Position
   :members:

.. autoclass:: slider.bit_enum.BitEnum
   :members:

Predictions
-----------

.. autofunction:: slider.model.train.train_model

.. autofunction:: slider.model.train.train_from_replay_directory

.. autofunction:: slider.model.train.test_model_from_replay_directory

.. autoclass:: slider.model.model.OsuModel
   :members:

.. autoclass:: slider.model.model.MLPRegressor
   :members:

.. autofunction:: slider.model.features.extract_features

.. autofunction:: slider.model.features.extract_feature_array

.. autofunction:: slider.model.features.extract_from_replay_directory
