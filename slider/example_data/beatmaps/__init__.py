from pkg_resources import resource_filename

from slider import Beatmap


def example_beatmap(name):
    """Load one of the example beatmaps.

    Parameters
    ----------
    name : str
        The name of the example file to open.
    """
    return Beatmap.from_path(
        resource_filename(
            __name__,
            name,
        ),
    )


_sendan_life_versions = frozenset({
    "Easy",
    "Normal",
    "Little's Hard",
    "Little's Insane",
    "Extra",
    "Crystal's Garakowa",
})


def sendan_life(version="Crystal's Garakowa"):
    """Load Sendan Life beatmap.

    Parameters
    ----------
    version : str
        The version to load.

    Returns
    -------
    sendan_life : Beatmap
        The beatmap object.
    """
    if version not in _sendan_life_versions:
        raise ValueError(
            f'unknown version {version}, options: {set(_sendan_life_versions)}'
        )

    return example_beatmap(
        f'Remo Prototype[CV Hanamori Yumiri] - Sendan Life (Narcissu)'
        f' [{version}].osu'
    )
