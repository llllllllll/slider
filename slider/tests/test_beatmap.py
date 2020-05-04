from datetime import timedelta
from math import isclose

import pytest

import slider.example_data.beatmaps
import slider.beatmap
import slider.curve
from slider.position import Position
from datetime import timedelta
from math import isclose
import numpy as np


@pytest.fixture
def beatmap():
    return slider.example_data.beatmaps.miiro_vs_ai_no_scenario('Tatoe')


def test_version(beatmap):
    assert beatmap.format_version == 14


def test_display_name(beatmap):
    assert beatmap.display_name == (
        'AKINO from bless4 & CHiCO with HoneyWorks - MIIRO '
        'vs. Ai no Scenario [Tatoe]'
    )


def test_parse_section_general(beatmap):
    assert beatmap.audio_filename == "tatoe.mp3"
    assert beatmap.audio_lead_in == timedelta()
    assert beatmap.preview_time == timedelta(milliseconds=6538)
    assert not beatmap.countdown
    assert beatmap.sample_set == "Normal"
    assert beatmap.stack_leniency == 0.7
    assert beatmap.mode == 0
    assert not beatmap.letterbox_in_breaks
    assert not beatmap.widescreen_storyboard


def test_parse_section_editor(beatmap):
    assert beatmap.distance_spacing == 1.1
    assert beatmap.beat_divisor == 6
    assert beatmap.grid_size == 4
    assert beatmap.timeline_zoom == 1.8


def test_parse_section_metadata(beatmap):
    assert beatmap.title == "MIIRO vs. Ai no Scenario"
    assert beatmap.title_unicode == "海色 vs. アイのシナリオ"
    assert beatmap.artist == "AKINO from bless4 & CHiCO with HoneyWorks"
    assert beatmap.artist_unicode == (
        "AKINO from bless4 & CHiCO with HoneyWorks"
    )
    assert beatmap.creator == "monstrata"
    assert beatmap.version == "Tatoe"
    assert beatmap.source == ""
    assert beatmap.tags == [
        'kyshiro',
        'sukinathan',
        'ktgster',
        'pishifat',
        'smoothie',
        'world',
        'walaowey',
        'toybot',
        'sheela901',
        'yuii-',
        'Sharkie',
        'みいろ',
        'tv',
        'size',
        'opening',
        'kantai',
        'collection',
        'kancolle',
        'fleet',
        'girls',
        'magic',
        'kaito',
        '1412',
        'まじっく快斗1412',
        '艦隊これくしょん',
        '-艦これ-'
    ]
    assert beatmap.beatmap_id == 735272
    assert beatmap.beatmap_set_id == 325158


def test_parse_section_difficulty(beatmap):
    assert beatmap.hp_drain_rate == 6.5
    assert beatmap.circle_size == 4
    assert beatmap.overall_difficulty == 9
    assert beatmap.approach_rate == 9.5
    assert beatmap.slider_multiplier == 1.8
    assert beatmap.slider_tick_rate == 1


def test_parse_section_timing_points(beatmap):
    # currently only checking the first timing point
    timing_points_0 = beatmap.timing_points[0]
    assert timing_points_0.offset == timedelta()
    assert isclose(timing_points_0.ms_per_beat, 307.692307692308)
    assert timing_points_0.meter == 4
    # sample_set and sample_type omitted, see #56
    assert timing_points_0.volume == 60
    # inherited is not in class parameter
    assert timing_points_0.kiai_mode == 0

def test_parse_section_hit_objects(beatmap):
    # Only hit object 0 tested for now
    hit_objects_0 = beatmap.hit_objects(stacking=False)[0]
    assert hit_objects_0.position == Position(x=243, y=164)
    assert hit_objects_0.time == timedelta(milliseconds=1076)
    # Hit object note `type` is done by subclassing HitObject
    assert isinstance(hit_objects_0, slider.beatmap.Slider)
    # Slider specific parameters
    assert hit_objects_0.end_time == timedelta(milliseconds=1173)
    assert hit_objects_0.hitsound == 0
    assert isinstance(hit_objects_0.curve, slider.curve.Linear)
    assert hit_objects_0.curve.points == [Position(x=243, y=164),
                                          Position(x=301, y=175)]
    assert round(hit_objects_0.curve.req_length) == 45
    assert isclose(hit_objects_0.length, 45.0000017166138)
    assert hit_objects_0.ticks == 2
    assert hit_objects_0.num_beats == 0.3125
    assert hit_objects_0.tick_rate == 1.0
    assert isclose(hit_objects_0.ms_per_beat, 307.692307692308)
    assert hit_objects_0.edge_sounds == [2, 0]
    assert hit_objects_0.edge_additions == ['0:0', '0:0']
    assert hit_objects_0.addition == "0:0:0:0:"


def test_hit_objects_stacking(beatmap):
    hit_objects_stacked = beatmap.hit_objects(stacking=True)
    assert len(hit_objects_stacked) == len(beatmap.hit_objects(stacking=False))
    assert np.array_equal(np.nonzero([h.stack_height for h in hit_objects_stacked]),
                          [[7, 8, 10, 11, 16, 28, 29, 31, 35, 36, 38, 46, 50, 51,
                            52, 54, 56, 58, 59, 60, 61, 62, 64, 67, 70, 71, 98,
                            102, 106, 111, 114, 116, 122, 124, 125, 126, 128, 129,
                            134, 135, 137, 138, 140, 141, 142, 144, 145, 147, 150,
                            156, 162, 177, 180, 183, 191, 193, 194, 195, 196, 197,
                            198, 199, 201, 203, 207, 208, 209, 210, 211, 213, 214,
                            228, 240, 241, 242, 245, 246, 249, 251, 252, 253, 256,
                            257, 258, 260, 261, 262, 263, 266, 283, 284, 288, 289,
                            290, 291, 294, 295, 297, 301, 302, 303, 304, 305, 307,
                            308, 309, 310, 313, 316, 320, 321, 322, 324, 325, 329]])
    assert hit_objects_stacked[7].stack_height == 1
    assert hit_objects_stacked[7].position == Position(x=281.352, y=223.352)
    assert hit_objects_stacked[31].stack_height == -1
    assert hit_objects_stacked[31].position == Position(x=286.648, y=230.648)

def test_hit_objects_hard_rock(beatmap):
    # Only hit object 0 tested for now
    hit_objects_hard_rock_0 = beatmap.hit_objects(hard_rock=True, stacking=False)[0]
    assert hit_objects_hard_rock_0.position == Position(x=243, y=220)
    assert hit_objects_hard_rock_0.curve.points == [Position(x=243, y=220),
                                          Position(x=301, y=209)]


def test_ar(beatmap):
    assert beatmap.ar() == 9.5


def test_bpm_min(beatmap):
    assert beatmap.bpm_min() == 180


def test_bpm_max(beatmap):
    assert beatmap.bpm_max() == 195


def test_cs(beatmap):
    assert beatmap.cs() == 4


def test_hp(beatmap):
    assert beatmap.hp() == 6.5  # issue #57


def test_od(beatmap):
    assert beatmap.od() == 9
