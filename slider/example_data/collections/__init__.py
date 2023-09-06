from pkg_resources import resource_filename

from slider import CollectionDB


def example_collection(name):
    """Load one of the example collection dbs.

    Parameters
    ----------
    name : str
        The name of the example file to open.
    """
    return CollectionDB.from_path(
        resource_filename(
            __name__,
            name,
        ),
    )


def test_db():
    """Load the testing collection db.

    Returns
    -------
    test_db : CollectionDB
        The collection db object.
    """
    return example_collection('test.db')
