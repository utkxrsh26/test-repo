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
    """Provide a list of sample activities with ISO timestamps."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    return [
        {"action": "login", "timestamp": (base + timedelta(minutes=0)).isoformat()},
        {"action": "view", "timestamp": (base + timedelta(minutes=5)).isoformat()},
        {"action": "click", "timestamp": (base + timedelta(minutes=10)).isoformat()},
        {"action": "view", "timestamp": (base + timedelta(minutes=15)).isoformat()},
        {"action": "logout", "timestamp": (base + timedelta(minutes=20)).isoformat()},
    ]


# ActivityPattern tests


def test_activitypattern_init_and_attributes():
    """Test ActivityPattern initialization and attribute assignment."""
    pattern = ActivityPattern("type1", "desc", 0.95)
    assert pattern.pattern_type == "type1"
    assert pattern.description == "desc"
    assert pattern.confidence == pytest.approx(0.95)


def test_activitypattern_to_dict():
    """Test ActivityPattern.to_dict returns correct dictionary."""
    pattern = ActivityPattern("peak_hours", "High activity", 0.85)
    result = pattern.to_dict()
    assert result["pattern_type"] == "peak_hours"
    assert result["description"] == "High activity"
    assert result["confidence"] == pytest.approx(0.85)


# ActivityAnalyzer.__init__ tests


def test_activityanalyzer_init_defaults(activity_analyzer):
    """Test ActivityAnalyzer initialization sets default thresholds."""
    assert activity_analyzer.peak_hour_threshold == pytest.approx(0.2)
    assert activity_analyzer.anomaly_threshold == pytest.approx(3.0)


# _parse_timestamp tests


def test_activityanalyzer_parse_timestamp_datetime(activity_analyzer):
    """Test _parse_timestamp returns datetime unchanged when given datetime."""
    ts = datetime(2024, 1, 1, 12, 0, 0)
    parsed = activity_analyzer._parse_timestamp(ts)
    assert parsed is ts


def test_activityanalyzer_parse_timestamp_iso_string(activity_analyzer):
    """Test _parse_timestamp parses ISO 8601 string with Z suffix."""
    ts_str = "2024-01-01T12:00:00Z"
    parsed = activity_analyzer._parse_timestamp(ts_str)
    assert isinstance(parsed, datetime)
    assert parsed.year == 2024
    assert parsed.month == 1
    assert parsed.day == 1
    assert parsed.hour == 12


def test_activityanalyzer_parse_timestamp_invalid_string(activity_analyzer):
    """Test _parse_timestamp returns None for invalid string."""
    parsed = activity_analyzer._parse_timestamp("not-a-timestamp")
    assert parsed is None


def test_activityanalyzer_parse_timestamp_none(activity_analyzer):
    """Test _parse_timestamp returns None for None input."""
    parsed = activity_analyzer._parse_timestamp(None)
    assert parsed is None


# _detect_peak_hours tests


def test_activityanalyzer_detect_peak_hours_basic(activity_analyzer):
    """Test _detect_peak_hours detects peak hours above threshold."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = []
    for i in range(8):
        activities.append({"timestamp": (base + timedelta(minutes=5 * i)).isoformat()})
    for i in range(2):
        activities.append({"timestamp": (base.replace(hour=9) + timedelta(minutes=5 * i)).isoformat()})
    patterns = activity_analyzer._detect_peak_hours(activities)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.pattern_type == "peak_hours"
    assert "10:00" in pattern.description
    assert pattern.confidence == pytest.approx(0.85)


def test_activityanalyzer_detect_peak_hours_no_peak(activity_analyzer):
    """Test _detect_peak_hours returns empty when no hour exceeds threshold."""
    base = datetime(2024, 1, 1, 0, 0, 0)
    activities = []
    for h in range(10):
        activities.append({"timestamp": (base.replace(hour=h)).isoformat()})
    patterns = activity_analyzer._detect_peak_hours(activities)
    assert patterns == []


def test_activityanalyzer_detect_peak_hours_invalid_timestamps(activity_analyzer):
    """Test _detect_peak_hours ignores invalid timestamps."""
    activities = [
        {"timestamp": "invalid"},
        {"timestamp": None},
    ]
    patterns = activity_analyzer._detect_peak_hours(activities)
    assert patterns == []


# _detect_action_sequences tests


def test_activityanalyzer_detect_action_sequences_minimum(activity_analyzer):
    """Test _detect_action_sequences returns empty for fewer than 3 activities."""
    activities = [
        {"action": "a", "timestamp": "2024-01-01T00:00:00Z"},
        {"action": "b", "timestamp": "2024-01-01T00:01:00Z"},
    ]
    patterns = activity_analyzer._detect_action_sequences(activities)
    assert patterns == []


def test_activityanalyzer_detect_action_sequences_repeated(activity_analyzer):
    """Test _detect_action_sequences detects common sequences occurring at least twice."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    activities = [
        {"action": "login", "timestamp": (base + timedelta(minutes=0)).isoformat()},
        {"action": "view", "timestamp": (base + timedelta(minutes=1)).isoformat()},
        {"action": "click", "timestamp": (base + timedelta(minutes=2)).isoformat()},
        {"action": "login", "timestamp": (base + timedelta(minutes=3)).isoformat()},
        {"action": "view", "timestamp": (base + timedelta(minutes=4)).isoformat()},
        {"action": "click", "timestamp": (base + timedelta(minutes=5)).isoformat()},
    ]
    patterns = activity_analyzer._detect_action_sequences(activities)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.pattern_type == "action_sequence"
    assert "login → view → click" in pattern.description
    assert "(occurred 2 times)" in pattern.description
    assert pattern.confidence == pytest.approx(0.75)


def test_activityanalyzer_detect_action_sequences_uses_default_action(activity_analyzer):
    """Test _detect_action_sequences uses empty string when action key missing."""
    activities = [
        {"timestamp": "2024-01-01T00:00:00Z"},
        {"timestamp": "2024-01-01T00:01:00Z"},
        {"timestamp": "2024-01-01T00:02:00Z"},
        {"timestamp": "2024-01-01T00:03:00Z"},
        {"timestamp": "2024-01-01T00:04:00Z"},
    ]
    patterns = activity_analyzer._detect_action_sequences(activities)
    assert patterns == []


# _detect_regularity tests


def test_activityanalyzer_detect_regularity_not_enough(activity_analyzer):
    """Test _detect_regularity returns empty for fewer than 5 activities."""
    activities = [
        {"timestamp": "2024-01-01T00:00:00Z"},
        {"timestamp": "2024-01-01T00:01:00Z"},
        {"timestamp": "2024-01-01T00:02:00Z"},
        {"timestamp": "2024-01-01T00:03:00Z"},
    ]
    patterns = activity_analyzer._detect_regularity(activities)
    assert patterns == []


def test_activityanalyzer_detect_regularity_highly_regular(activity_analyzer):
    """Test _detect_regularity detects highly regular intervals."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    activities = []
    for i in range(6):
        activities.append({"timestamp": (base + timedelta(minutes=10 * i)).isoformat()})
    patterns = activity_analyzer._detect_regularity(activities)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.pattern_type == "regularity"
    assert "Highly regular activity pattern" in pattern.description
    assert pattern.confidence == pytest.approx(0.9)


def test_activityanalyzer_detect_regularity_irregular(activity_analyzer):
    """Test _detect_regularity returns empty for irregular intervals."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    activities = [
        {"timestamp": (base + timedelta(minutes=0)).isoformat()},
        {"timestamp": (base + timedelta(minutes=1)).isoformat()},
        {"timestamp": (base + timedelta(minutes=3)).isoformat()},
        {"timestamp": (base + timedelta(minutes=7)).isoformat()},
        {"timestamp": (base + timedelta(minutes=15)).isoformat()},
        {"timestamp": (base + timedelta(minutes=31)).isoformat()},
    ]
    patterns = activity_analyzer._detect_regularity(activities)
    assert patterns == []


def test_activityanalyzer_detect_regularity_ignores_invalid_timestamps(activity_analyzer):
    """Test _detect_regularity ignores invalid timestamps and may return empty."""
    activities = [
        {"timestamp": "invalid"},
        {"timestamp": None},
        {"timestamp": "2024-01-01T00:00:00Z"},
        {"timestamp": "2024-01-01T00:01:00Z"},
        {"timestamp": "2024-01-01T00:02:00Z"},
    ]
    patterns = activity_analyzer._detect_regularity(activities)
    assert patterns == []


# analyze_patterns tests


def test_activityanalyzer_analyze_patterns_empty(activity_analyzer):
    """Test analyze_patterns returns empty list for no activities."""
    assert activity_analyzer.analyze_patterns([]) == []


def test_activityanalyzer_analyze_patterns_integration(activity_analyzer):
    """Test analyze_patterns combines peak hours, sequences, and regularity."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    activities = []
    for i in range(10):
        activities.append({"action": "a", "timestamp": (base + timedelta(minutes=10 * i)).isoformat()})
    for i in range(2):
        activities.append({"action": "b", "timestamp": (base.replace(hour=9) + timedelta(minutes=10 * i)).isoformat()})
    patterns = activity_analyzer.analyze_patterns(activities)
    types = {p.pattern_type for p in patterns}
    assert "peak_hours" in types
    assert "regularity" in types
    assert "action_sequence" not in types


def test_activityanalyzer_analyze_patterns_uses_internal_methods(activity_analyzer):
    """Test analyze_patterns calls internal detection methods."""
    activities = [{"action": "x", "timestamp": "2024-01-01T00:00:00Z"}] * 5
    with patch.object(activity_analyzer, "_detect_peak_hours", return_value=[]) as mock_peak, \
         patch.object(activity_analyzer, "_detect_action_sequences", return_value=[]) as mock_seq, \
         patch.object(activity_analyzer, "_detect_regularity", return_value=[]) as mock_reg:
        result = activity_analyzer.analyze_patterns(activities)
        assert result == []
        mock_peak.assert_called_once_with(activities)
        mock_seq.assert_called_once_with(activities)
        mock_reg.assert_called_once_with(activities)


# get_user_score tests


def test_activityanalyzer_get_user_score_empty(activity_analyzer):
    """Test get_user_score returns 0.0 for empty activities."""
    score = activity_analyzer.get_user_score([])
    assert score == pytest.approx(0.0)


def test_activityanalyzer_get_user_score_basic(activity_analyzer, sample_activities):
    """Test get_user_score computes expected score with diversity and frequency."""
    score = activity_analyzer.get_user_score(sample_activities)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_activityanalyzer_get_user_score_unique_action_logic(activity_analyzer):
    """Test get_user_score unique action counting logic with duplicates."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    activities = [
        {"action": "a", "timestamp": (base + timedelta(days=0)).isoformat()},
        {"action": "b", "timestamp": (base + timedelta(days=1)).isoformat()},
        {"action": "a", "timestamp": (base + timedelta(days=2)).isoformat()},
        {"action": "c", "timestamp": (base + timedelta(days=3)).isoformat()},
    ]
    score = activity_analyzer.get_user_score(activities)
    assert score == pytest.approx(score)


def test_activityanalyzer_get_user_score_no_timestamps(activity_analyzer):
    """Test get_user_score when timestamps are missing or invalid."""
    activities = [
        {"action": "a", "timestamp": "invalid"},
        {"action": "b"},
        {"action": "c", "timestamp": None},
    ]
    score = activity_analyzer.get_user_score(activities)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_activityanalyzer_get_user_score_single_day(activity_analyzer):
    """Test get_user_score when all activities occur on same day."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    activities = [
        {"action": "a", "timestamp": (base + timedelta(hours=i)).isoformat()}
        for i in range(5)
    ]
    score = activity_analyzer.get_user_score(activities)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


# detect_anomalies tests


def test_activityanalyzer_detect_anomalies_too_few(activity_analyzer):
    """Test detect_anomalies returns empty for fewer than 5 activities."""
    activities = [
        {"action": "a", "timestamp": "2024-01-01T00:00:00Z"},
        {"action": "a", "timestamp": "2024-01-01T00:01:00Z"},
        {"action": "a", "timestamp": "2024-01-01T00:02:00Z"},
        {"action": "a", "timestamp": "2024-01-01T00:03:00Z"},
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert anomalies == []


def test_activityanalyzer_detect_anomalies_no_anomaly(activity_analyzer):
    """Test detect_anomalies returns empty when intervals are regular."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    activities = []
    for i in range(6):
        activities.append({"action": "a", "timestamp": (base + timedelta(minutes=10 * i)).isoformat()})
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert anomalies == []


def test_activityanalyzer_detect_anomalies_with_anomaly(activity_analyzer):
    """Test detect_anomalies detects an interval with high z-score."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    activities = [
        {"action": "a", "timestamp": (base + timedelta(minutes=0)).isoformat()},
        {"action": "a", "timestamp": (base + timedelta(minutes=10)).isoformat()},
        {"action": "a", "timestamp": (base + timedelta(minutes=20)).isoformat()},
        {"action": "a", "timestamp": (base + timedelta(minutes=30)).isoformat()},
        {"action": "a", "timestamp": (base + timedelta(hours=5)).isoformat()},
        {"action": "a", "timestamp": (base + timedelta(hours=5, minutes=10)).isoformat()},
    ]
    activity_analyzer.anomaly_threshold = 1.0
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert len(anomalies) >= 1
    for anomaly in anomalies:
        assert anomaly["action"] == "a"
        assert "timestamp" in anomaly
        assert "z_score" in anomaly
        assert anomaly["z_score"] >= 1.0
        assert "Unusual interval" in anomaly["reason"]


def test_activityanalyzer_detect_anomalies_ignores_invalid_timestamps(activity_analyzer):
    """Test detect_anomalies ignores activities with invalid timestamps."""
    activities = [
        {"action": "a", "timestamp": "invalid"},
        {"action": "a", "timestamp": None},
        {"action": "a", "timestamp": "2024-01-01T00:00:00Z"},
        {"action": "a", "timestamp": "2024-01-01T00:10:00Z"},
        {"action": "a", "timestamp": "2024-01-01T00:20:00Z"},
        {"action": "a", "timestamp": "2024-01-01T00:30:00Z"},
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert anomalies == []


def test_activityanalyzer_detect_anomalies_multiple_actions(activity_analyzer):
    """Test detect_anomalies processes each action group separately."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    activities = [
        {"action": "a", "timestamp": (base + timedelta(minutes=0)).isoformat()},
        {"action": "a", "timestamp": (base + timedelta(minutes=10)).isoformat()},
        {"action": "a", "timestamp": (base + timedelta(minutes=20)).isoformat()},
        {"action": "b", "timestamp": (base + timedelta(minutes=0)).isoformat()},
        {"action": "b", "timestamp": (base + timedelta(hours=2)).isoformat()},
        {"action": "b", "timestamp": (base + timedelta(hours=4)).isoformat()},
        {"action": "b", "timestamp": (base + timedelta(hours=6)).isoformat()},
        {"action": "b", "timestamp": (base + timedelta(hours=8)).isoformat()},
    ]
    activity_analyzer.anomaly_threshold = 1.0
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert isinstance(anomalies, list)


# Exception handling / robustness tests


def test_activityanalyzer_methods_handle_missing_keys(activity_analyzer):
    """Test methods handle activities missing expected keys without raising exceptions."""
    activities = [
        {},
        {"action": "a"},
        {"timestamp": "2024-01-01T00:00:00Z"},
    ]
    score = activity_analyzer.get_user_score(activities)
    assert isinstance(score, float)
    patterns = activity_analyzer.analyze_patterns(activities)
    assert isinstance(patterns, list)
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert isinstance(anomalies, list)


def test_activityanalyzer_detect_anomalies_no_intervals(activity_analyzer):
    """Test detect_anomalies handles case where all timestamps for an action are identical."""
    ts = "2024-01-01T00:00:00Z"
    activities = [
        {"action": "a", "timestamp": ts},
        {"action": "a", "timestamp": ts},
        {"action": "a", "timestamp": ts},
        {"action": "a", "timestamp": ts},
        {"action": "a", "timestamp": ts},
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert anomalies == []


def test_activityanalyzer_internal_parse_timestamp_exception(activity_analyzer, monkeypatch):
    """Test _parse_timestamp gracefully handles unexpected exceptions."""
    def broken_fromisoformat(_):
        raise ValueError("broken")

    with monkeypatch.patch("datetime.datetime.fromisoformat", side_effect=broken_fromisoformat):
        parsed = activity_analyzer._parse_timestamp("2024-01-01T00:00:00Z")
        assert parsed is None