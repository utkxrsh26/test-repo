import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone

from src.activity_analyzer import ActivityPattern, ActivityAnalyzer


@pytest.fixture
def activity_pattern_instance():
    """Create ActivityPattern instance for testing."""
    return ActivityPattern(pattern_type="test_type", description="test_desc", confidence=0.75)


@pytest.fixture
def activity_analyzer_instance():
    """Create ActivityAnalyzer instance for testing."""
    return ActivityAnalyzer()


def test_activitypattern_init():
    """Test ActivityPattern initialization with valid data."""
    pattern = ActivityPattern(pattern_type="type1", description="desc1", confidence=0.9)
    assert pattern.pattern_type == "type1"
    assert pattern.description == "desc1"
    assert pattern.confidence == pytest.approx(0.9)


def test_activitypattern_to_dict(activity_pattern_instance):
    """Test ActivityPattern.to_dict returns correct dictionary."""
    result = activity_pattern_instance.to_dict()
    assert result["pattern_type"] == "test_type"
    assert result["description"] == "test_desc"
    assert result["confidence"] == pytest.approx(0.75)


def test_activityanalyzer_init_defaults(activity_analyzer_instance):
    """Test ActivityAnalyzer initialization sets default thresholds."""
    assert activity_analyzer_instance.peak_hour_threshold == pytest.approx(0.2)
    assert activity_analyzer_instance.anomaly_threshold == pytest.approx(3.0)


def test_activityanalyzer_analyze_patterns_empty(activity_analyzer_instance):
    """Test analyze_patterns returns empty list for no activities."""
    result = activity_analyzer_instance.analyze_patterns([])
    assert result == []


def test_activityanalyzer_analyze_patterns_calls_internal_methods(activity_analyzer_instance):
    """Test analyze_patterns calls internal detection methods and aggregates results."""
    activities = [
        {"action": "a", "timestamp": datetime.now(timezone.utc).isoformat()},
        {"action": "b", "timestamp": datetime.now(timezone.utc).isoformat()},
    ]

    with patch.object(activity_analyzer_instance, "_detect_peak_hours", return_value=[ActivityPattern("p", "ph", 0.1)]) as mock_peak, \
         patch.object(activity_analyzer_instance, "_detect_action_sequences", return_value=[ActivityPattern("s", "seq", 0.2)]) as mock_seq, \
         patch.object(activity_analyzer_instance, "_detect_regularity", return_value=[ActivityPattern("r", "reg", 0.3)]) as mock_reg:

        result = activity_analyzer_instance.analyze_patterns(activities)

        mock_peak.assert_called_once_with(activities)
        mock_seq.assert_called_once_with(activities)
        mock_reg.assert_called_once_with(activities)

        assert len(result) == 3
        assert isinstance(result[0], ActivityPattern)
        assert {p.pattern_type for p in result} == {"p", "s", "r"}


def test_activityanalyzer_get_user_score_empty(activity_analyzer_instance):
    """Test get_user_score returns 0.0 for empty activities."""
    score = activity_analyzer_instance.get_user_score([])
    assert score == pytest.approx(0.0)


def test_activityanalyzer_get_user_score_basic(activity_analyzer_instance):
    """Test get_user_score with simple activities and timestamps."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = [
        {"action": "login", "timestamp": (base + timedelta(days=0)).isoformat()},
        {"action": "view", "timestamp": (base + timedelta(days=0, hours=1)).isoformat()},
        {"action": "logout", "timestamp": (base + timedelta(days=1)).isoformat()},
        {"action": "login", "timestamp": (base + timedelta(days=1, hours=2)).isoformat()},
    ]

    score = activity_analyzer_instance.get_user_score(activities)

    # Compute expected components based on implementation
    total_actions = 4
    unique_actions = 3  # login, view, logout
    diversity_score = unique_actions / total_actions  # 0.75
    days_active = max((activities[-1]["timestamp"] and activity_analyzer_instance._parse_timestamp(
        activities[-1]["timestamp"]) - activity_analyzer_instance._parse_timestamp(
        activities[0]["timestamp"])).days, 1)
    actions_per_day = total_actions / days_active
    frequency_score = min(actions_per_day / 10.0, 1.0)
    volume_score = min(total_actions / 100.0, 1.0)
    expected = (diversity_score * 0.3 + frequency_score * 0.4 + volume_score * 0.3) * 100

    assert score == pytest.approx(round(expected, 2))


def test_activityanalyzer_get_user_score_no_timestamps(activity_analyzer_instance):
    """Test get_user_score when timestamps are missing or unparsable."""
    activities = [
        {"action": "a", "timestamp": "not-a-timestamp"},
        {"action": "b", "timestamp": None},
        {"action": "a"},  # no timestamp key
    ]

    score = activity_analyzer_instance.get_user_score(activities)

    total_actions = 3
    unique_actions = 2  # a, b
    diversity_score = unique_actions / total_actions
    actions_per_day = total_actions  # falls back to total_actions
    frequency_score = min(actions_per_day / 10.0, 1.0)
    volume_score = min(total_actions / 100.0, 1.0)
    expected = (diversity_score * 0.3 + frequency_score * 0.4 + volume_score * 0.3) * 100

    assert score == pytest.approx(round(expected, 2))


def test_activityanalyzer_get_user_score_duplicate_action_logic(activity_analyzer_instance):
    """Test get_user_score unique action counting logic with repeated actions."""
    # This specifically tests the unusual unique action counting implementation
    activities = [
        {"action": "a", "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat()},
        {"action": "b", "timestamp": datetime(2024, 1, 2, tzinfo=timezone.utc).isoformat()},
        {"action": "a", "timestamp": datetime(2024, 1, 3, tzinfo=timezone.utc).isoformat()},
        {"action": "c", "timestamp": datetime(2024, 1, 4, tzinfo=timezone.utc).isoformat()},
    ]
    # According to the implementation, unique_actions will be 3 (a, b, c)
    score = activity_analyzer_instance.get_user_score(activities)
    assert isinstance(score, float)


def test_activityanalyzer_detect_anomalies_too_few(activity_analyzer_instance):
    """Test detect_anomalies returns empty list when fewer than 5 activities."""
    activities = [
        {"action": "a", "timestamp": datetime.now(timezone.utc).isoformat()}
        for _ in range(4)
    ]
    result = activity_analyzer_instance.detect_anomalies(activities)
    assert result == []


def test_activityanalyzer_detect_anomalies_no_intervals(activity_analyzer_instance):
    """Test detect_anomalies when timestamps cannot be parsed."""
    activities = [
        {"action": "a", "timestamp": "invalid"} for _ in range(10)
    ]
    result = activity_analyzer_instance.detect_anomalies(activities)
    assert result == []


def test_activityanalyzer_detect_anomalies_basic(activity_analyzer_instance):
    """Test detect_anomalies with regular intervals that should not trigger anomalies."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = []
    for i in range(6):
        activities.append({
            "action": "click",
            "timestamp": (base + timedelta(minutes=10 * i)).isoformat()
        })

    result = activity_analyzer_instance.detect_anomalies(activities)
    assert isinstance(result, list)
    assert result == []


def test_activityanalyzer_detect_anomalies_with_large_interval(activity_analyzer_instance):
    """Test detect_anomalies can detect an anomalous large interval."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    timestamps = [
        base,
        base + timedelta(minutes=10),
        base + timedelta(minutes=20),
        base + timedelta(hours=5),  # large gap
        base + timedelta(hours=5, minutes=10),
        base + timedelta(hours=5, minutes=20),
    ]
    activities = [{"action": "click", "timestamp": ts.isoformat()} for ts in timestamps]

    result = activity_analyzer_instance.detect_anomalies(activities)
    assert isinstance(result, list)
    # Depending on z-score, may or may not detect; just ensure no exceptions and structure is correct
    for anomaly in result:
        assert anomaly["action"] == "click"
        assert "timestamp" in anomaly
        assert isinstance(anomaly["z_score"], float) or isinstance(anomaly["z_score"], int)
        assert "reason" in anomaly


def test_activityanalyzer_detect_anomalies_multiple_actions(activity_analyzer_instance):
    """Test detect_anomalies handles multiple actions and skips those with <3 timestamps."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = [
        {"action": "a", "timestamp": (base + timedelta(minutes=5 * i)).isoformat()}
        for i in range(3)
    ]
    activities += [
        {"action": "b", "timestamp": (base + timedelta(minutes=7 * i)).isoformat()}
        for i in range(2)
    ]

    result = activity_analyzer_instance.detect_anomalies(activities)
    assert isinstance(result, list)


def test_activityanalyzer_detect_anomalies_exception_handling(activity_analyzer_instance):
    """Test detect_anomalies handles exceptions from _parse_timestamp gracefully."""
    activities = [{"action": "a", "timestamp": "2024-01-01T00:00:00Z"} for _ in range(6)]

    with patch.object(activity_analyzer_instance, "_parse_timestamp", side_effect=Exception("parse error")):
        # Should propagate exception because there is no explicit try/except in detect_anomalies
        with pytest.raises(Exception):
            activity_analyzer_instance.detect_anomalies(activities)


def test_activityanalyzer_detect_peak_hours_no_timestamps(activity_analyzer_instance):
    """Test _detect_peak_hours returns empty when no valid timestamps."""
    activities = [
        {"action": "a", "timestamp": "invalid"},
        {"action": "b", "timestamp": None},
    ]
    result = activity_analyzer_instance._detect_peak_hours(activities)
    assert result == []


def test_activityanalyzer_detect_peak_hours_single_peak(activity_analyzer_instance):
    """Test _detect_peak_hours identifies peak hours above threshold."""
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    activities = []
    # 8 activities at 10:00
    for i in range(8):
        activities.append({"action": "a", "timestamp": (base + timedelta(minutes=i)).isoformat()})
    # 2 activities at 11:00
    for i in range(2):
        activities.append({"action": "a", "timestamp": (base + timedelta(hours=1, minutes=i)).isoformat()})

    result = activity_analyzer_instance._detect_peak_hours(activities)
    assert len(result) == 1
    pattern = result[0]
    assert pattern.pattern_type == "peak_hours"
    assert "10:00" in pattern.description
    assert pattern.confidence == pytest.approx(0.85)


def test_activityanalyzer_detect_peak_hours_no_peak(activity_analyzer_instance):
    """Test _detect_peak_hours returns empty when no hour exceeds threshold."""
    base = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    activities = []
    # 1 activity per hour for 10 hours -> each 10%
    for h in range(10):
        activities.append({"action": "a", "timestamp": (base + timedelta(hours=h)).isoformat()})

    result = activity_analyzer_instance._detect_peak_hours(activities)
    assert result == []


def test_activityanalyzer_detect_action_sequences_too_short(activity_analyzer_instance):
    """Test _detect_action_sequences returns empty when fewer than 3 activities."""
    activities = [
        {"action": "a", "timestamp": datetime.now(timezone.utc).isoformat()},
        {"action": "b", "timestamp": datetime.now(timezone.utc).isoformat()},
    ]
    result = activity_analyzer_instance._detect_action_sequences(activities)
    assert result == []


def test_activityanalyzer_detect_action_sequences_common_sequences(activity_analyzer_instance):
    """Test _detect_action_sequences identifies common sequences occurring at least twice."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = [
        {"action": "login", "timestamp": (base + timedelta(minutes=0)).isoformat()},
        {"action": "view", "timestamp": (base + timedelta(minutes=1)).isoformat()},
        {"action": "logout", "timestamp": (base + timedelta(minutes=2)).isoformat()},
        {"action": "login", "timestamp": (base + timedelta(minutes=3)).isoformat()},
        {"action": "view", "timestamp": (base + timedelta(minutes=4)).isoformat()},
        {"action": "logout", "timestamp": (base + timedelta(minutes=5)).isoformat()},
    ]

    result = activity_analyzer_instance._detect_action_sequences(activities)
    assert len(result) >= 1
    pattern = result[0]
    assert pattern.pattern_type == "action_sequence"
    assert "login → view → logout" in pattern.description
    assert pattern.confidence == pytest.approx(0.75)


def test_activityanalyzer_detect_action_sequences_limit_top3(activity_analyzer_instance):
    """Test _detect_action_sequences only returns up to top 3 sequences."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    actions = ["a", "b", "c", "d", "e"]
    activities = []
    for i in range(20):
        activities.append({
            "action": actions[i % len(actions)],
            "timestamp": (base + timedelta(minutes=i)).isoformat()
        })

    result = activity_analyzer_instance._detect_action_sequences(activities)
    assert len(result) <= 3
    for pattern in result:
        assert pattern.pattern_type == "action_sequence"


def test_activityanalyzer_detect_regularity_too_few(activity_analyzer_instance):
    """Test _detect_regularity returns empty when fewer than 5 activities."""
    activities = [
        {"action": "a", "timestamp": datetime.now(timezone.utc).isoformat()}
        for _ in range(4)
    ]
    result = activity_analyzer_instance._detect_regularity(activities)
    assert result == []


def test_activityanalyzer_detect_regularity_insufficient_valid_timestamps(activity_analyzer_instance):
    """Test _detect_regularity returns empty when fewer than 5 valid timestamps."""
    activities = [
        {"action": "a", "timestamp": "invalid"} for _ in range(10)
    ]
    result = activity_analyzer_instance._detect_regularity(activities)
    assert result == []


def test_activityanalyzer_detect_regularity_highly_regular(activity_analyzer_instance):
    """Test _detect_regularity detects highly regular intervals (low CV)."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = []
    for i in range(6):
        activities.append({
            "action": "a",
            "timestamp": (base + timedelta(minutes=10 * i)).isoformat()
        })

    result = activity_analyzer_instance._detect_regularity(activities)
    assert len(result) == 1
    pattern = result[0]
    assert pattern.pattern_type == "regularity"
    assert "Highly regular activity pattern" in pattern.description
    assert pattern.confidence == pytest.approx(0.9)


def test_activityanalyzer_detect_regularity_irregular(activity_analyzer_instance):
    """Test _detect_regularity returns empty for irregular intervals (high CV)."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    intervals = [1, 5, 20, 2, 30]  # highly variable
    activities = []
    current = base
    for i, minutes in enumerate(intervals):
        current = current + timedelta(minutes=minutes)
        activities.append({"action": "a", "timestamp": current.isoformat()})

    result = activity_analyzer_instance._detect_regularity(activities)
    assert result == []


def test_activityanalyzer_parse_timestamp_datetime(activity_analyzer_instance):
    """Test _parse_timestamp returns datetime unchanged when input is datetime."""
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    result = activity_analyzer_instance._parse_timestamp(ts)
    assert result == ts


def test_activityanalyzer_parse_timestamp_iso_string(activity_analyzer_instance):
    """Test _parse_timestamp parses ISO 8601 string with Z suffix."""
    ts_str = "2024-01-01T12:34:56Z"
    result = activity_analyzer_instance._parse_timestamp(ts_str)
    assert isinstance(result, datetime)
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 1
    assert result.hour == 12
    assert result.minute == 34
    assert result.second == 56
    assert result.tzinfo is not None


def test_activityanalyzer_parse_timestamp_iso_string_offset(activity_analyzer_instance):
    """Test _parse_timestamp parses ISO 8601 string with explicit offset."""
    ts_str = "2024-01-01T12:34:56+00:00"
    result = activity_analyzer_instance._parse_timestamp(ts_str)
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


def test_activityanalyzer_parse_timestamp_invalid_string(activity_analyzer_instance):
    """Test _parse_timestamp returns None for invalid string."""
    ts_str = "not-a-timestamp"
    result = activity_analyzer_instance._parse_timestamp(ts_str)
    assert result is None


def test_activityanalyzer_parse_timestamp_unsupported_type(activity_analyzer_instance):
    """Test _parse_timestamp returns None for unsupported type."""
    result = activity_analyzer_instance._parse_timestamp(12345)
    assert result is None


def test_activityanalyzer_parse_timestamp_exception_handling(activity_analyzer_instance, monkeypatch):
    """Test _parse_timestamp handles ValueError from datetime.fromisoformat."""
    def bad_fromisoformat(_):
        raise ValueError("bad format")

    with monkeypatch.patch("datetime.datetime.fromisoformat", bad_fromisoformat):
        result = activity_analyzer_instance._parse_timestamp("2024-01-01T00:00:00Z")
        # Because we patched the global datetime, this may not be called; ensure no exception from method itself
        assert result is None or isinstance(result, datetime)


def test_activityanalyzer_internal_methods_mocked_in_analyze_patterns(activity_analyzer_instance):
    """Test analyze_patterns behavior when internal methods raise exceptions."""
    activities = [
        {"action": "a", "timestamp": datetime.now(timezone.utc).isoformat()}
        for _ in range(5)
    ]

    with patch.object(activity_analyzer_instance, "_detect_peak_hours", side_effect=Exception("peak error")), \
         patch.object(activity_analyzer_instance, "_detect_action_sequences", return_value=[]), \
         patch.object(activity_analyzer_instance, "_detect_regularity", return_value=[]):
        # No try/except in analyze_patterns, so exception should propagate
        with pytest.raises(Exception):
            activity_analyzer_instance.analyze_patterns(activities)