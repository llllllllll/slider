from slider import Beatmap
from datetime import timedelta

tatoe_path = "data/AKINO from bless4 & CHiCO with " + \
        "HoneyWorks - MIIRO vs. Ai no Scenario (monstrata) [Tatoe].osu"


def test_beatmap_parameters():
    beatmap = Beatmap.from_path(tatoe_path)
    assert beatmap.format_version == 14

    # [General]
    assert beatmap.audio_filename == "tatoe.mp3"
    assert beatmap.audio_lead_in == timedelta()
    assert beatmap.preview_time == timedelta(milliseconds=6538)
    assert beatmap.countdown == False
    assert beatmap.sample_set == "Normal"
    assert beatmap.stack_leniency == 0.7
    assert beatmap.mode == 0
    assert beatmap.letterbox_in_breaks == False
    assert beatmap.widescreen_storyboard == False

    # [Editor]
    assert beatmap.distance_spacing == 1.1
    assert beatmap.beat_divisor == 6
    assert beatmap.grid_size == 4
    assert beatmap.timeline_zoom == 1.8

    # [Metadata]
    assert beatmap.title == "MIIRO vs. Ai no Scenario"
    assert beatmap.title_unicode == "海色 vs. アイのシナリオ"
    assert beatmap.artist == "AKINO from bless4 & CHiCO with HoneyWorks"
    assert beatmap.artist_unicode == \
           "AKINO from bless4 & CHiCO with HoneyWorks"
    assert beatmap.creator == "monstrata"
    assert beatmap.version == "Tatoe"
    assert beatmap.source == ""
    assert beatmap.tags == \
           ['kyshiro', 'sukinathan', 'ktgster', 'pishifat', 'smoothie',
            'world', 'walaowey', 'toybot', 'sheela901', 'yuii-', 'Sharkie',
            'みいろ', 'tv', 'size', 'opening', 'kantai', 'collection',
            'kancolle', 'fleet', 'girls', 'magic', 'kaito', '1412',
            'まじっく快斗1412', '艦隊これくしょん', '-艦これ-']
    assert beatmap.beatmap_id == 735272
    assert beatmap.beatmap_set_id == 325158

    # [Difficulty]
    assert beatmap.hp_drain_rate == 6.5
    assert beatmap.circle_size == 4
    assert beatmap.overall_difficulty == 9
    assert beatmap.approach_rate == 9.5
    assert beatmap.slider_multiplier == 1.8
    assert beatmap.slider_tick_rate == 1

    # [Events] (skipped)
    # [TimingPoints] (the first one at least)
    timing_points_0 = beatmap.timing_points[0]
    assert timing_points_0.offset == timedelta()
    assert timing_points_0.ms_per_beat == 307.692307692308
    assert timing_points_0.meter == 4
    # sample_set and sample_type omitted, see #56
    assert timing_points_0.volume == 60
    # inherited is not in class parameter
    assert timing_points_0.kiai_mode == 0

    # [Colours] (skipped)
    # [HitObjects]
    hit_objects_0 = beatmap.hit_objects[0]
    assert hit_objects_0.position.x == 243
    assert hit_objects_0.position.y == 164
    assert hit_objects_0.time == timedelta(milliseconds=1076)


