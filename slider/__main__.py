import click

from . import Library


@click.group()
def main():
    """Slider utilities.
    """


@main.command()
@click.option(
    '--beatmaps',
    help='The path to the beatmap directory.',
    required=True,
)
@click.option(
    '--recurse/--no-recurse',
    help='Recurse through ``path`` searching for beatmaps?',
    default=True,
)
@click.option(
    '--progress/--no-progress',
    help='Show a progress bar?',
    default=True,
)
def library(beatmaps, recurse, progress):
    """Create a slider database from a directory of beatmaps.
    """
    Library.create_db(beatmaps, recurse=recurse, show_progress=progress)


if __name__ == '__main__':
    main()
