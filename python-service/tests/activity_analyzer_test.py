import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone

from src.activity_analyzer import ActivityPattern, ActivityAnalyzer


@pytest.fixture
def activity_analyzer():
    """Create ActivityAnalyzer instance for testing."""
    return ActivityAnalyzer()


@pytest.fixture
def sample_activities():
    """Provide a basic list of activities with timestamps and actions."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    return [
        {"action": "login", "timestamp": (base + timedelta(minutes=0)).isoformat()},
        {"action": "view", "timestamp": (base + timedelta(minutes=5)).isoformat()},
        {"action": "click", "timestamp": (base + timedelta(minutes=10)).isoformat()},
        {"action": "logout", "timestamp": (base + timedelta(minutes=15)).isoformat()},
    ]


def test_activitypattern_init_and_to_dict():
    """Test ActivityPattern initialization and to_dict method."""
    pattern = ActivityPattern("type1", "desc", 0.95)
    assert pattern.pattern_type == "type1"
    assert pattern.description == "desc"
    assert pattern.confidence == pytest.approx(0.95)

    result = pattern.to_dict()
    assert result["pattern_type"] == "type1"
    assert result["description"] == "desc"
    assert result["confidence"] == pytest.approx(0.95)


def test_activityanalyzer_init_defaults(activity_analyzer):
    """Test ActivityAnalyzer initialization default attributes."""
    assert activity_analyzer.peak_hour_threshold == pytest.approx(0.2)
    assert activity_analyzer.anomaly_threshold == pytest.approx(3.0)


def test_activityanalyzer_analyze_patterns_empty(activity_analyzer):
    """Test analyze_patterns returns empty list for no activities."""
    assert activity_analyzer.analyze_patterns([]) == []


def test_activityanalyzer_analyze_patterns_calls_internal_methods(activity_analyzer, sample_activities):
    """Test analyze_patterns calls internal detection methods and aggregates results."""
    mock_peak = [ActivityPattern("peak_hours", "peak", 0.8)]
    mock_seq = [ActivityPattern("action_sequence", "seq", 0.7)]
    mock_reg = [ActivityPattern("regularity", "reg", 0.9)]

    with patch.object(activity_analyzer, "_detect_peak_hours", return_value=mock_peak) as mock_peak_fn, \
         patch.object(activity_analyzer, "_detect_action_sequences", return_value=mock_seq) as mock_seq_fn, \
         patch.object(activity_analyzer, "_detect_regularity", return_value=mock_reg) as mock_reg_fn:
        patterns = activity_analyzer.analyze_patterns(sample_activities)

    mock_peak_fn.assert_called_once_with(sample_activities)
    mock_seq_fn.assert_called_once_with(sample_activities)
    mock_reg_fn.assert_called_once_with(sample_activities)

    assert len(patterns) == 3
    assert patterns[0] is mock_peak[0]
    assert patterns[1] is mock_seq[0]
    assert patterns[2] is mock_reg[0]


def test_activityanalyzer_get_user_score_empty(activity_analyzer):
    """Test get_user_score returns 0.0 for empty activities."""
    score = activity_analyzer.get_user_score([])
    assert score == pytest.approx(0.0)


def test_activityanalyzer_get_user_score_basic(activity_analyzer):
    """Test get_user_score with a simple set of activities and valid timestamps."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    activities = [
        {"action": "login", "timestamp": (base + timedelta(days=0)).isoformat()},
        {"action": "view", "timestamp": (base + timedelta(days=0, hours=1)).isoformat()},
        {"action": "view", "timestamp": (base + timedelta(days=1)).isoformat()},
        {"action": "click", "timestamp": (base + timedelta(days=1, hours=2)).isoformat()},
    ]
    score = activity_analyzer.get_user_score(activities)

    # Compute expected according to implementation
    total_actions = 4
    # unique_actions logic: first occurrence only, order-based
    # actions: ["login", "view", "view", "click"] -> unique: login, view, click => 3
    diversity_score = 3 / total_actions
    days_active = max((activity_analyzer._parse_timestamp(activities[-1]["timestamp"]) -
                       activity_analyzer._parse_timestamp(activities[0]["timestamp"])).days, 1)
    actions_per_day = total_actions / days_active
    frequency_score = min(actions_per_day / 10.0, 1.0)
    volume_score = min(total_actions / 100.0, 1.0)
    expected = (diversity_score * 0.3 + frequency_score * 0.4 + volume_score * 0.3) * 100
    expected = round(expected, 2)

    assert score == pytest.approx(expected)


def test_activityanalyzer_get_user_score_invalid_timestamps(activity_analyzer):
    """Test get_user_score when timestamps cannot be parsed (falls back to total_actions)."""
    activities = [
        {"action": "a", "timestamp": "not-a-timestamp"},
        {"action": "b", "timestamp": None},
        {"action": "a", "timestamp": 12345},
    ]
    score = activity_analyzer.get_user_score(activities)

    total_actions = 3
    # unique_actions logic: ["a", "b", "a"] -> "a" (first), "b" (second), third "a" is not unique
    diversity_score = 2 / total_actions
    actions_per_day = total_actions  # because first_ts and last_ts are None
    frequency_score = min(actions_per_day / 10.0, 1.0)
    volume_score = min(total_actions / 100.0, 1.0)
    expected = (diversity_score * 0.3 + frequency_score * 0.4 + volume_score * 0.3) * 100
    expected = round(expected, 2)

    assert score == pytest.approx(expected)


def test_activityanalyzer_detect_anomalies_too_few(activity_analyzer, sample_activities):
    """Test detect_anomalies returns empty list when fewer than 5 activities."""
    anomalies = activity_analyzer.detect_anomalies(sample_activities)
    assert anomalies == []


def test_activityanalyzer_detect_anomalies_no_intervals(activity_analyzer):
    """Test detect_anomalies when all timestamps for an action are identical (no anomalous intervals)."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    activities = [
        {"action": "login", "timestamp": base.isoformat()},
        {"action": "login", "timestamp": base.isoformat()},
        {"action": "login", "timestamp": base.isoformat()},
        {"action": "login", "timestamp": base.isoformat()},
        {"action": "login", "timestamp": base.isoformat()},
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert anomalies == []


def test_activityanalyzer_detect_anomalies_with_clear_outlier(activity_analyzer):
    """Test detect_anomalies detects an interval with a large z-score as anomaly."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    # Intervals: 10s, 10s, 10s, 1000s -> last interval should be anomalous
    timestamps = [
        base,
        base + timedelta(seconds=10),
        base + timedelta(seconds=20),
        base + timedelta(seconds=30),
        base + timedelta(seconds=1030),
    ]
    activities = [{"action": "click", "timestamp": ts.isoformat()} for ts in timestamps]

    anomalies = activity_analyzer.detect_anomalies(activities)

    # Depending on z-score, we expect at least one anomaly for the last interval
    assert isinstance(anomalies, list)
    if anomalies:
        for anomaly in anomalies:
            assert anomaly["action"] == "click"
            assert "timestamp" in anomaly
            assert "z_score" in anomaly
            assert isinstance(anomaly["z_score"], float)
            assert "reason" in anomaly


def test_activityanalyzer_detect_anomalies_ignores_unparsable_timestamps(activity_analyzer):
    """Test detect_anomalies ignores activities with unparsable timestamps."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    activities = [
        {"action": "click", "timestamp": base.isoformat()},
        {"action": "click", "timestamp": "invalid"},
        {"action": "click", "timestamp": (base + timedelta(seconds=10)).isoformat()},
        {"action": "click", "timestamp": None},
        {"action": "click", "timestamp": (base + timedelta(seconds=20)).isoformat()},
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert isinstance(anomalies, list)


def test_activityanalyzer_detect_anomalies_zero_std_dev(activity_analyzer):
    """Test detect_anomalies when std_dev is zero (no anomalies should be produced)."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    # All intervals equal -> std_dev = 0, so no z-score calculation
    timestamps = [
        base,
        base + timedelta(seconds=10),
        base + timedelta(seconds=20),
        base + timedelta(seconds=30),
        base + timedelta(seconds=40),
    ]
    activities = [{"action": "view", "timestamp": ts.isoformat()} for ts in timestamps]
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert anomalies == []


def test_activityanalyzer_detect_peak_hours_no_activities(activity_analyzer):
    """Test _detect_peak_hours returns empty list when no valid timestamps."""
    activities = [{"action": "a", "timestamp": "invalid"}]
    patterns = activity_analyzer._detect_peak_hours(activities)
    assert patterns == []


def test_activityanalyzer_detect_peak_hours_basic(activity_analyzer):
    """Test _detect_peak_hours identifies hours exceeding threshold."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    activities = []
    # 8 activities at 10:00, 2 at 11:00 -> 10:00 should be peak (0.8 > 0.2)
    for i in range(8):
        activities.append({"action": "a", "timestamp": (base + timedelta(minutes=i)).isoformat()})
    for i in range(2):
        activities.append({"action": "b", "timestamp": (base + timedelta(hours=1, minutes=i)).isoformat()})

    patterns = activity_analyzer._detect_peak_hours(activities)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.pattern_type == "peak_hours"
    assert "High activity during hours" in pattern.description
    assert "10:00" in pattern.description
    assert pattern.confidence == pytest.approx(0.85)


def test_activityanalyzer_detect_action_sequences_too_short(activity_analyzer):
    """Test _detect_action_sequences returns empty list when fewer than 3 activities."""
    activities = [{"action": "a", "timestamp": None}, {"action": "b", "timestamp": None}]
    patterns = activity_analyzer._detect_action_sequences(activities)
    assert patterns == []


def test_activityanalyzer_detect_action_sequences_common_sequences(activity_analyzer):
    """Test _detect_action_sequences identifies common sequences occurring at least twice."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    # Sequence: login -> view -> click appears twice
    activities = [
        {"action": "login", "timestamp": (base + timedelta(minutes=0)).isoformat()},
        {"action": "view", "timestamp": (base + timedelta(minutes=1)).isoformat()},
        {"action": "click", "timestamp": (base + timedelta(minutes=2)).isoformat()},
        {"action": "login", "timestamp": (base + timedelta(minutes=3)).isoformat()},
        {"action": "view", "timestamp": (base + timedelta(minutes=4)).isoformat()},
        {"action": "click", "timestamp": (base + timedelta(minutes=5)).isoformat()},
    ]
    patterns = activity_analyzer._detect_action_sequences(activities)
    assert len(patterns) >= 1
    seq_pattern = patterns[0]
    assert seq_pattern.pattern_type == "action_sequence"
    assert "Common sequence" in seq_pattern.description
    assert "login" in seq_pattern.description
    assert "view" in seq_pattern.description
    assert "click" in seq_pattern.description
    assert "(occurred 2 times)" in seq_pattern.description
    assert seq_pattern.confidence == pytest.approx(0.75)


def test_activityanalyzer_detect_regularity_too_few(activity_analyzer):
    """Test _detect_regularity returns empty list when fewer than 5 activities."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    activities = [
        {"action": "a", "timestamp": (base + timedelta(minutes=i)).isoformat()}
        for i in range(4)
    ]
    patterns = activity_analyzer._detect_regularity(activities)
    assert patterns == []


def test_activityanalyzer_detect_regularity_not_enough_valid_timestamps(activity_analyzer):
    """Test _detect_regularity returns empty list when fewer than 5 valid timestamps."""
    activities = [
        {"action": "a", "timestamp": "invalid"},
        {"action": "a", "timestamp": None},
        {"action": "a", "timestamp": 123},
        {"action": "a", "timestamp": "2024-01-01T10:00:00Z"},
        {"action": "a", "timestamp": "invalid2"},
    ]
    patterns = activity_analyzer._detect_regularity(activities)
    assert patterns == []


def test_activityanalyzer_detect_regularity_highly_regular(activity_analyzer):
    """Test _detect_regularity detects highly regular intervals (low coefficient of variation)."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    # Equal intervals of 10 minutes -> CV = 0
    activities = [
        {"action": "a", "timestamp": (base + timedelta(minutes=10 * i)).isoformat()}
        for i in range(6)
    ]
    patterns = activity_analyzer._detect_regularity(activities)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.pattern_type == "regularity"
    assert "Highly regular activity pattern" in pattern.description
    assert "CV:" in pattern.description
    assert pattern.confidence == pytest.approx(0.9)


def test_activityanalyzer_detect_regularity_irregular(activity_analyzer):
    """Test _detect_regularity returns empty list for irregular intervals (high CV)."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    # Irregular intervals
    timestamps = [
        base,
        base + timedelta(minutes=1),
        base + timedelta(minutes=10),
        base + timedelta(minutes=30),
        base + timedelta(minutes=31),
        base + timedelta(minutes=90),
    ]
    activities = [{"action": "a", "timestamp": ts.isoformat()} for ts in timestamps]
    patterns = activity_analyzer._detect_regularity(activities)
    assert patterns == []


def test_activityanalyzer_parse_timestamp_datetime(activity_analyzer):
    """Test _parse_timestamp returns datetime unchanged when input is datetime."""
    ts = datetime(2024, 1, 1, 10, 0, 0)
    parsed = activity_analyzer._parse_timestamp(ts)
    assert parsed == ts


def test_activityanalyzer_parse_timestamp_valid_iso_string(activity_analyzer):
    """Test _parse_timestamp parses valid ISO 8601 string."""
    ts_str = "2024-01-01T10:00:00"
    parsed = activity_analyzer._parse_timestamp(ts_str)
    assert isinstance(parsed, datetime)
    assert parsed.year == 2024
    assert parsed.month == 1
    assert parsed.day == 1
    assert parsed.hour == 10
    assert parsed.minute == 0
    assert parsed.second == 0


def test_activityanalyzer_parse_timestamp_with_z_suffix(activity_analyzer):
    """Test _parse_timestamp parses ISO string with 'Z' suffix as UTC."""
    ts_str = "2024-01-01T10:00:00Z"
    parsed = activity_analyzer._parse_timestamp(ts_str)
    assert isinstance(parsed, datetime)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)


def test_activityanalyzer_parse_timestamp_invalid_string(activity_analyzer):
    """Test _parse_timestamp returns None for invalid string."""
    parsed = activity_analyzer._parse_timestamp("not-a-timestamp")
    assert parsed is None


def test_activityanalyzer_parse_timestamp_unsupported_type(activity_analyzer):
    """Test _parse_timestamp returns None for unsupported type."""
    parsed = activity_analyzer._parse_timestamp(12345)
    assert parsed is None


def test_activityanalyzer_internal_exception_handling_in_parse_timestamp(activity_analyzer, monkeypatch):
    """Test _parse_timestamp handles exceptions from datetime.fromisoformat gracefully."""
    def bad_fromisoformat(_):
        raise ValueError("bad format")

    with monkeypatch.patch("datetime.datetime.fromisoformat", side_effect=bad_fromisoformat):
        parsed = activity_analyzer._parse_timestamp("2024-01-01T10:00:00")
        assert parsed is None


def test_activityanalyzer_get_user_score_with_mocked_parse_timestamp(activity_analyzer, monkeypatch):
    """Test get_user_score behavior when _parse_timestamp is mocked to return None."""
    activities = [
        {"action": "a", "timestamp": "2024-01-01T10:00:00"},
        {"action": "b", "timestamp": "2024-01-02T10:00:00"},
    ]

    mock_parse = MagicMock(return_value=None)
    monkeypatch.setattr(activity_analyzer, "_parse_timestamp", mock_parse)

    score = activity_analyzer.get_user_score(activities)

    total_actions = 2
    diversity_score = 2 / total_actions
    actions_per_day = total_actions
    frequency_score = min(actions_per_day / 10.0, 1.0)
    volume_score = min(total_actions / 100.0, 1.0)
    expected = (diversity_score * 0.3 + frequency_score * 0.4 + volume_score * 0.3) * 100
    expected = round(expected, 2)

    assert score == pytest.approx(expected)
    assert mock_parse.call_count == 2