from everest.earthquakes import _event_key, _event_text


def test_earthquake_event_key_uses_time_coordinates_and_magnitude():
    text = '2026-09-25 09:46:30 19.341 -155.354 28 3.2 ISLAND OF HAWAII'
    assert _event_key(text, 'earthquake-03') == 'quake:2026-09-25 09:46'


def test_usgs_and_emsc_share_the_same_event_identity():
    usgs = '3.2 16 km SW of Volcano, Hawaii 2026-09-25 09:46:30 (UTC) 27.7 km'
    emsc = '2026-09-25 09:46:30 19.341 -155.354 28 3.2 ISLAND OF HAWAII, HAWAII'
    assert _event_key(usgs, 'earthquake-02') == _event_key(emsc, 'earthquake-03')


def test_revised_magnitudes_keep_the_same_cross_source_event_identity():
    usgs = '5.3 Vanuatu region 2026-09-25 11:12:15 (UTC) 24.0 km'
    geofon = '5.1 Vanuatu Islands Region 2026-09-25 11:12:15.3 (≤2 h ago) 10 *'
    assert _event_key(usgs, 'earthquake-02') == _event_key(geofon, 'earthquake-05')


def test_normalized_event_text_excludes_dynamic_relative_time():
    assert _event_text('2026-09-25 12:12:54', 2.6, 38.7, 23.4, 13, 'GREECE') == (
        'M2.6 | 2026-09-25 12:12:54 UTC | 38.7, 23.4 | 13 km | GREECE'
    )


def test_usgs_auto_update_status_is_not_an_earthquake_event():
    rows = ['Auto Update 2026-09-25 12:43:54 (UTC)', '5.3 Vanuatu region 2026-09-25 11:12:15 (UTC) 24.0 km']
    events = [x for x in rows if not x.startswith('Auto Update') and '2026-' in x]
    assert events == [rows[1]]
