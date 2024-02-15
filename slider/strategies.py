from datetime import timedelta

from hypothesis import given, settings, note
from hypothesis.strategies import (integers, text, timedeltas as _timedeltas, booleans, floats as _floats,
    composite, from_type, lists, just, one_of, sampled_from)

from slider import (Beatmap, GameMode, TimingPoint, Position, Circle,
    Slider, Spinner, HoldNote)
from slider.curve import Curve

def floats(*args, **kwargs):
    # I don't really want to deal with these edge cases right now.
    return _floats(*args, allow_nan=False, allow_infinity=False, **kwargs)

@composite
def timing_points(draw):
    return TimingPoint(
        offset=draw(timedeltas()),
        ms_per_beat=draw(floats()),
        meter=draw(integers()),
        sample_type=draw(integers()),
        sample_set=draw(integers()),
        volume=draw(integers(0, 100)),
        parent=draw(timing_points() | just(None)),
        kiai_mode=draw(booleans())
    )

def timedeltas(*, reasonable=False):
    if not reasonable:
        return _timedeltas()
    min_value = timedelta(seconds=2)
    max_value = timedelta(seconds=60)
    return _timedeltas(min_value, max_value)

@composite
def positions(draw, *, reasonable=False):
    return Position(
        x=draw(integers(0, 512) if reasonable else integers()),
        y=draw(integers(0, 384) if reasonable else integers())
    )

@composite
def circles(draw, *, reasonable=False):
    return Circle(
        position=draw(positions(reasonable=reasonable)),
        time=draw(timedeltas(reasonable=reasonable)),
        hitsound=draw(integers()),
        new_combo=draw(booleans()),
        combo_skip=draw(integers())
    )

@composite
def spinners(draw, *, reasonable=False):
    return Spinner(
        position=draw(positions(reasonable=reasonable)),
        time=draw(timedeltas(reasonable=reasonable)),
        hitsound=draw(integers()),
        end_time=draw(timedeltas(reasonable=reasonable)),
        addition=draw(text()),
        new_combo=draw(booleans()),
        combo_skip=draw(integers())
    )

@composite
def sliders(draw, *, reasonable=False):
    return Slider(
        position=draw(positions(reasonable=reasonable)),
        time=draw(timedeltas(reasonable=reasonable)),
        end_time=draw(timedeltas(reasonable=reasonable)),
        hitsound=draw(integers()),
        curve=draw(curves(reasonable=reasonable)),
        # avoid divide by 0, I think
        repeat=draw(integers(min_value=1)),
        length=draw(floats(2, 200) if reasonable else floats()),
        ticks=draw(integers()),
        num_beats=draw(integers()),
        tick_rate=draw(floats()),
        ms_per_beat=draw(integers()),
        edge_sounds=draw(lists(integers())),
        edge_additions=draw(lists(text())),
        addition=draw(text()),
        new_combo=draw(booleans()),
        combo_skip=draw(integers())
    )

@composite
def curves(draw, *, reasonable=False):
    # kind = draw(sampled_from(["B", "L", "C", "P"]))
    # TODO fix issues with arctan2 in perfect curve type
    kind = draw(sampled_from(["B", "L", "C"]))


    min_points = 0
    # catmull needs at least one point.
    # TODO do other curve types have restrictions? probably.
    if kind == "C":
        min_points = 1

    points = draw(lists(positions(), min_size=min_points))
    return Curve.from_kind_and_points(
        kind=kind,
        points=points,
        req_length=draw(floats(1, 100) if reasonable else floats())
    )

def hit_objects(reasonable):
    if reasonable:
        # sliders are hard to make sane.
        return one_of(
            circles(reasonable=reasonable),
            spinners(reasonable=reasonable)
        )

    # TODO HoldNote?
    return one_of(
        circles(), sliders(), spinners()
    )

@composite
def beatmaps(draw, reasonable=False):
    hit_objs = draw(lists(hit_objects(reasonable=reasonable), min_size=20 if reasonable else 0))
    hit_objs = sorted(hit_objs, key=lambda hitobj: hitobj.time)
    return Beatmap(
        format_version=draw(integers()),
        audio_filename=draw(text()),
        audio_lead_in=draw(timedeltas()),
        preview_time=draw(timedeltas()),
        countdown=draw(booleans()),
        sample_set=draw(text()),
        stack_leniency=draw(floats(1, 2) if reasonable else floats()),
        mode=draw(from_type(GameMode)),
        letterbox_in_breaks=draw(booleans()),
        widescreen_storyboard=draw(booleans()),
        bookmarks=draw(lists(timedeltas())),
        distance_spacing=draw(floats()),
        beat_divisor=draw(integers()),
        grid_size=draw(integers()),
        timeline_zoom=draw(floats()),
        title=draw(text("ascii")),
        title_unicode=draw(text()),
        artist=draw(text("ascii")),
        artist_unicode=draw(text()),
        creator=draw(text()),
        version=draw(text()),
        source=draw(text()),
        tags=draw(lists(text())),
        beatmap_id=draw(integers() | just(None)),
        beatmap_set_id=draw(integers() | just(None)),
        hp_drain_rate=draw(floats(1, 10) if reasonable else floats()),
        circle_size=draw(floats(1, 10) if reasonable else floats()),
        overall_difficulty=draw(floats(1, 10) if reasonable else floats()),
        approach_rate=draw(floats(1, 10) if reasonable else floats()),
        # avoid div by 0, I think
        slider_multiplier=draw(floats(0, exclude_min=True)),
        # avoid div by 0, I think
        slider_tick_rate=draw(floats(0, exclude_min=True)),
        # TODO is minimum 1 timing point a requirement?
        timing_points=draw(lists(timing_points(), min_size=1)),
        hit_objects=hit_objs
    )
