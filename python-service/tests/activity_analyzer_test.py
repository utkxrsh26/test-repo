import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

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
        {"action": "logout", "timestamp": (base + timedelta(minutes=15)).isoformat()},
    ]


# -------------------- ActivityPattern tests --------------------


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
    assert result == {
        "pattern_type": "peak_hours",
        "description": "High activity",
        "confidence": pytest.approx(0.85),
    }


# -------------------- ActivityAnalyzer.__init__ tests --------------------


def test_activityanalyzer_init_defaults(activity_analyzer):
    """Test ActivityAnalyzer initialization sets default thresholds."""
    assert activity_analyzer.peak_hour_threshold == pytest.approx(0.2)
    assert activity_analyzer.anomaly_threshold == pytest.approx(3.0)


# -------------------- _parse_timestamp tests --------------------


def test_activityanalyzer_parse_timestamp_datetime(activity_analyzer):
    """Test _parse_timestamp returns datetime unchanged when given datetime."""
    ts = datetime(2024, 1, 1, 12, 0, 0)
    parsed = activity_analyzer._parse_timestamp(ts)
    assert parsed == ts


def test_activityanalyzer_parse_timestamp_iso_string(activity_analyzer):
    """Test _parse_timestamp parses ISO 8601 string."""
    ts_str = "2024-01-01T12:00:00"
    parsed = activity_analyzer._parse_timestamp(ts_str)
    assert isinstance(parsed, datetime)
    assert parsed.year == 2024
    assert parsed.month == 1
    assert parsed.day == 1
    assert parsed.hour == 12
    assert parsed.minute == 0
    assert parsed.second == 0


def test_activityanalyzer_parse_timestamp_iso_string_with_z(activity_analyzer):
    """Test _parse_timestamp parses ISO 8601 string with Z suffix."""
    ts_str = "2024-01-01T12:00:00Z"
    parsed = activity_analyzer._parse_timestamp(ts_str)
    assert isinstance(parsed, datetime)
    assert parsed.tzinfo is not None
    assert parsed.hour == 12


def test_activityanalyzer_parse_timestamp_invalid_string(activity_analyzer):
    """Test _parse_timestamp returns None for invalid string."""
    ts_str = "not-a-timestamp"
    parsed = activity_analyzer._parse_timestamp(ts_str)
    assert parsed is None


def test_activityanalyzer_parse_timestamp_unsupported_type(activity_analyzer):
    """Test _parse_timestamp returns None for unsupported type."""
    parsed = activity_analyzer._parse_timestamp(12345)
    assert parsed is None


# -------------------- _detect_peak_hours tests --------------------


def test_activityanalyzer_detect_peak_hours_basic(activity_analyzer):
    """Test _detect_peak_hours identifies peak hours above threshold."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = []
    for i in range(8):
        activities.append({"action": "a", "timestamp": (base + timedelta(hours=0, minutes=i)).isoformat()})
    for i in range(2):
        activities.append({"action": "a", "timestamp": (base + timedelta(hours=1, minutes=i)).isoformat()})

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
    for h in range(5):
        activities.append({"action": "a", "timestamp": (base + timedelta(hours=h)).isoformat()})

    patterns = activity_analyzer._detect_peak_hours(activities)
    assert patterns == []


def test_activityanalyzer_detect_peak_hours_invalid_timestamps(activity_analyzer):
    """Test _detect_peak_hours ignores activities with invalid timestamps."""
    activities = [
        {"action": "a", "timestamp": "invalid"},
        {"action": "a", "timestamp": None},
    ]
    patterns = activity_analyzer._detect_peak_hours(activities)
    assert patterns == []


# -------------------- _detect_action_sequences tests --------------------


def test_activityanalyzer_detect_action_sequences_min_length(activity_analyzer):
    """Test _detect_action_sequences returns empty for fewer than 3 activities."""
    activities = [
        {"action": "a", "timestamp": "2024-01-01T00:00:00"},
        {"action": "b", "timestamp": "2024-01-01T00:01:00"},
    ]
    patterns = activity_analyzer._detect_action_sequences(activities)
    assert patterns == []


def test_activityanalyzer_detect_action_sequences_common_sequences(activity_analyzer):
    """Test _detect_action_sequences identifies repeated sequences."""
    activities = [
        {"action": "login"},
        {"action": "view"},
        {"action": "click"},
        {"action": "login"},
        {"action": "view"},
        {"action": "click"},
        {"action": "logout"},
    ]
    patterns = activity_analyzer._detect_action_sequences(activities)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.pattern_type == "action_sequence"
    assert "login → view → click" in pattern.description
    assert "(occurred 2 times)" in pattern.description
    assert pattern.confidence == pytest.approx(0.75)


def test_activityanalyzer_detect_action_sequences_uses_default_action(activity_analyzer):
    """Test _detect_action_sequences uses empty string when action missing."""
    activities = [
        {},
        {"action": "b"},
        {"action": "c"},
        {},
        {"action": "b"},
        {"action": "c"},
    ]
    patterns = activity_analyzer._detect_action_sequences(activities)
    assert len(patterns) == 1
    assert " → b → c" in patterns[0].description


# -------------------- _detect_regularity tests --------------------


def test_activityanalyzer_detect_regularity_not_enough_activities(activity_analyzer):
    """Test _detect_regularity returns empty for fewer than 5 activities."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = [
        {"timestamp": (base + timedelta(minutes=i)).isoformat()} for i in range(4)
    ]
    patterns = activity_analyzer._detect_regularity(activities)
    assert patterns == []


def test_activityanalyzer_detect_regularity_not_enough_valid_timestamps(activity_analyzer):
    """Test _detect_regularity returns empty when fewer than 5 valid timestamps."""
    activities = [
        {"timestamp": "invalid"},
        {"timestamp": "also-invalid"},
        {"timestamp": None},
        {"timestamp": "2024-01-01T00:00:00"},
        {"timestamp": "2024-01-01T00:01:00"},
    ]
    patterns = activity_analyzer._detect_regularity(activities)
    assert patterns == []


def test_activityanalyzer_detect_regularity_highly_regular(activity_analyzer):
    """Test _detect_regularity detects highly regular intervals."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = [
        {"timestamp": (base + timedelta(minutes=10 * i)).isoformat()} for i in range(6)
    ]
    patterns = activity_analyzer._detect_regularity(activities)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.pattern_type == "regularity"
    assert "Highly regular activity pattern" in pattern.description
    assert pattern.confidence == pytest.approx(0.9)


def test_activityanalyzer_detect_regularity_irregular(activity_analyzer):
    """Test _detect_regularity returns empty for irregular intervals."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    intervals = [1, 5, 20, 2, 30]
    activities = []
    current = base
    for inc in intervals:
        current += timedelta(minutes=inc)
        activities.append({"timestamp": current.isoformat()})
    patterns = activity_analyzer._detect_regularity(activities)
    assert patterns == []


# -------------------- analyze_patterns tests --------------------


def test_activityanalyzer_analyze_patterns_empty(activity_analyzer):
    """Test analyze_patterns returns empty list for no activities."""
    assert activity_analyzer.analyze_patterns([]) == []


def test_activityanalyzer_analyze_patterns_combines_detectors(activity_analyzer):
    """Test analyze_patterns aggregates patterns from all detectors."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = []
    for i in range(10):
        activities.append({"action": "a", "timestamp": (base + timedelta(minutes=10 * i)).isoformat()})
    for i in range(3):
        activities.append({"action": "b", "timestamp": (base + timedelta(hours=5, minutes=10 * i)).isoformat()})

    patterns = activity_analyzer.analyze_patterns(activities)
    assert isinstance(patterns, list)
    assert all(isinstance(p, ActivityPattern) for p in patterns)
    assert any(p.pattern_type == "peak_hours" for p in patterns)
    assert any(p.pattern_type == "regularity" for p in patterns)


def test_activityanalyzer_analyze_patterns_uses_internal_methods(activity_analyzer):
    """Test analyze_patterns calls internal detection methods."""
    activities = [{"action": "a", "timestamp": "2024-01-01T00:00:00"}] * 6
    with patch.object(activity_analyzer, "_detect_peak_hours", return_value=[]) as mock_peak, \
         patch.object(activity_analyzer, "_detect_action_sequences", return_value=[]) as mock_seq, \
         patch.object(activity_analyzer, "_detect_regularity", return_value=[]) as mock_reg:
        result = activity_analyzer.analyze_patterns(activities)
        assert result == []
        mock_peak.assert_called_once_with(activities)
        mock_seq.assert_called_once_with(activities)
        mock_reg.assert_called_once_with(activities)


# -------------------- get_user_score tests --------------------


def test_activityanalyzer_get_user_score_empty(activity_analyzer):
    """Test get_user_score returns 0.0 for empty activities."""
    score = activity_analyzer.get_user_score([])
    assert score == pytest.approx(0.0)


def test_activityanalyzer_get_user_score_basic(activity_analyzer):
    """Test get_user_score computes score based on diversity, frequency, and volume."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = []
    for i in range(10):
        activities.append({"action": "a", "timestamp": (base + timedelta(days=i)).isoformat()})
    score = activity_analyzer.get_user_score(activities)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_activityanalyzer_get_user_score_unique_action_logic(activity_analyzer):
    """Test get_user_score unique action counting logic with duplicates."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = [
        {"action": "a", "timestamp": (base + timedelta(days=0)).isoformat()},
        {"action": "b", "timestamp": (base + timedelta(days=1)).isoformat()},
        {"action": "a", "timestamp": (base + timedelta(days=2)).isoformat()},
        {"action": "c", "timestamp": (base + timedelta(days=3)).isoformat()},
    ]
    score = activity_analyzer.get_user_score(activities)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_activityanalyzer_get_user_score_missing_timestamps(activity_analyzer):
    """Test get_user_score falls back to total_actions when timestamps invalid."""
    activities = [
        {"action": "a", "timestamp": "invalid"},
        {"action": "b", "timestamp": None},
        {"action": "c"},
    ]
    score = activity_analyzer.get_user_score(activities)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_activityanalyzer_get_user_score_single_day_high_volume(activity_analyzer):
    """Test get_user_score caps frequency and volume scores at 1.0."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = [
        {"action": f"a{i}", "timestamp": (base + timedelta(minutes=i)).isoformat()}
        for i in range(150)
    ]
    score = activity_analyzer.get_user_score(activities)
    assert score == pytest.approx(100.0, rel=0.2)


# -------------------- detect_anomalies tests --------------------


def test_activityanalyzer_detect_anomalies_too_few_activities(activity_analyzer):
    """Test detect_anomalies returns empty list when fewer than 5 activities."""
    activities = [
        {"action": "a", "timestamp": "2024-01-01T00:00:00"},
        {"action": "a", "timestamp": "2024-01-01T00:01:00"},
        {"action": "a", "timestamp": "2024-01-01T00:02:00"},
        {"action": "a", "timestamp": "2024-01-01T00:03:00"},
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert anomalies == []


def test_activityanalyzer_detect_anomalies_no_anomalies(activity_analyzer):
    """Test detect_anomalies returns empty when intervals are consistent."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = []
    for i in range(6):
        activities.append({"action": "a", "timestamp": (base + timedelta(minutes=10 * i)).isoformat()})
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert anomalies == []


def test_activityanalyzer_detect_anomalies_with_anomaly(activity_analyzer):
    """Test detect_anomalies flags intervals with high z-score."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = [
        {"action": "a", "timestamp": (base + timedelta(minutes=0)).isoformat()},
        {"action": "a", "timestamp": (base + timedelta(minutes=10)).isoformat()},
        {"action": "a", "timestamp": (base + timedelta(minutes=20)).isoformat()},
        {"action": "a", "timestamp": (base + timedelta(hours=5)).isoformat()},
        {"action": "a", "timestamp": (base + timedelta(hours=5, minutes=10)).isoformat()},
        {"action": "a", "timestamp": (base + timedelta(hours=5, minutes=20)).isoformat()},
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert isinstance(anomalies, list)
    for anomaly in anomalies:
        assert "action" in anomaly
        assert "timestamp" in anomaly
        assert "z_score" in anomaly
        assert "reason" in anomaly
        assert isinstance(anomaly["z_score"], float)


def test_activityanalyzer_detect_anomalies_ignores_invalid_timestamps(activity_analyzer):
    """Test detect_anomalies ignores activities with invalid timestamps."""
    activities = [
        {"action": "a", "timestamp": "invalid"},
        {"action": "a", "timestamp": None},
        {"action": "a"},
        {"action": "a", "timestamp": "2024-01-01T00:00:00"},
        {"action": "a", "timestamp": "2024-01-01T00:10:00"},
        {"action": "a", "timestamp": "2024-01-01T00:20:00"},
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert anomalies == []


def test_activityanalyzer_detect_anomalies_multiple_actions(activity_analyzer):
    """Test detect_anomalies processes each action separately."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = []
    for i in range(6):
        activities.append({"action": "a", "timestamp": (base + timedelta(minutes=10 * i)).isoformat()})
    for i in range(6):
        activities.append({"action": "b", "timestamp": (base + timedelta(minutes=i * i)).isoformat()})
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert isinstance(anomalies, list)


# -------------------- exception / robustness tests --------------------


def test_activityanalyzer_methods_handle_missing_action_keys(activity_analyzer):
    """Test methods handle activities missing 'action' key without raising."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = [
        {"timestamp": (base + timedelta(minutes=i)).isoformat()} for i in range(6)
    ]
    score = activity_analyzer.get_user_score(activities)
    assert isinstance(score, float)
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert isinstance(anomalies, list)


def test_activityanalyzer_detect_anomalies_no_intervals(activity_analyzer):
    """Test detect_anomalies skips actions with fewer than 3 timestamps."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = [
        {"action": "a", "timestamp": (base + timedelta(minutes=0)).isoformat()},
        {"action": "a", "timestamp": (base + timedelta(minutes=10)).isoformat()},
        {"action": "b", "timestamp": (base + timedelta(minutes=20)).isoformat()},
        {"action": "b", "timestamp": (base + timedelta(minutes=30)).isoformat()},
        {"action": "c", "timestamp": (base + timedelta(minutes=40)).isoformat()},
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert anomalies == []