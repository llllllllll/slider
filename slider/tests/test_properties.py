from slider import Beatmap, Slider, Spinner, HoldNote
from slider.strategies import beatmaps

from hypothesis import given, settings


@given(beatmaps(reasonable=True))
@settings(report_multiple_bugs=False)
def test_packing(beatmap):
    # Pack the beatmap and parse it again to see if there is difference.
    packed_str = beatmap.pack()
    packed = Beatmap.parse(packed_str)
    # Since sections like Colours and Events are currently omitted by
    # ``Beatmap.parse``, these sections will be missing in .osu files
    # written back from parsed Beatmaps. Fortunately, without these
    # sections, rewritten .osu can still be recognized by osu! client.
    beatmap_attrs = [
        # General section fields
        'audio_filename', 'audio_lead_in', 'preview_time', 'countdown',
        'sample_set', 'stack_leniency', 'mode', 'letterbox_in_breaks',
        'widescreen_storyboard',
        # Editor section fields
        'distance_spacing', 'beat_divisor', 'grid_size', 'timeline_zoom',
        'bookmarks',
        # Metadata section fields
        'title', 'title_unicode', 'artist', 'artist_unicode', 'creator',
        'version', 'source', 'tags', 'beatmap_id', 'beatmap_set_id',
        # Difficulty section fields
        'hp_drain_rate', 'circle_size', 'overall_difficulty', 'approach_rate',
        'slider_multiplier', 'slider_tick_rate',
    ]
    hitobj_attrs = [
        'position', 'time', 'new_combo', 'combo_skip', 'hitsound', 'addition'
    ]
    slider_attrs = [
        'end_time', 'hitsound', 'repeat', 'length', 'ticks', 'num_beats',
        'tick_rate', 'ms_per_beat', 'edge_sounds', 'edge_additions', 'addition'
    ]
    timing_point_attrs = [
        'offset', 'ms_per_beat', 'meter', 'sample_type', 'sample_set',
        'volume', 'kiai_mode'
    ]

    def check_attrs(object1, object2, attr_list):
        for attr in attr_list:
            v1 = getattr(object1, attr)
            v2 = getattr(object2, attr)
            assert v1 == v2, (attr, v1, v2)

    def check_curve(curve1, curve2):
        assert type(curve1) is type(curve2)
        assert curve1.req_length == curve2.req_length
        for point1, point2 in zip(curve1.points, curve2.points):
            assert point1 == point2

    check_attrs(beatmap, packed, beatmap_attrs)

    # check hit objects
    assert len(beatmap._hit_objects) == len(packed._hit_objects)
    for hitobj1, hitobj2 in zip(beatmap._hit_objects, packed._hit_objects):
        assert type(hitobj1) is type(hitobj2)
        check_attrs(hitobj1, hitobj2, hitobj_attrs)

        if isinstance(hitobj1, Slider):
            check_attrs(hitobj1, hitobj2, slider_attrs)
            check_curve(hitobj1.curve, hitobj2.curve)
        elif isinstance(hitobj1, (Spinner, HoldNote)):
            # spinners / hold notes have an additional attribute `end_time`
            assert hitobj1.end_time == hitobj2.end_time
        # circles has no additional attributes beyond `hitobj_attrs`

    # check timing points
    assert len(beatmap.timing_points) == len(packed.timing_points)
    for tp1, tp2 in zip(beatmap.timing_points, packed.timing_points):
        check_attrs(tp1, tp2, timing_point_attrs)
        # make sure both timing points are either inherited or uninherited
        assert (tp1.parent is not None) == (tp2.parent is not None)
