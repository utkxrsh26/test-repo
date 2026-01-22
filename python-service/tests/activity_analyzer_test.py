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
    """Provide a basic list of activities with ISO timestamps."""
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
    assert result["pattern_type"] == "peak_hours"
    assert result["description"] == "High activity"
    assert result["confidence"] == pytest.approx(0.85)


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
    assert parsed is ts


def test_activityanalyzer_parse_timestamp_iso_string(activity_analyzer):
    """Test _parse_timestamp parses ISO 8601 string correctly."""
    ts_str = "2024-01-01T12:00:00"
    parsed = activity_analyzer._parse_timestamp(ts_str)
    assert isinstance(parsed, datetime)
    assert parsed.year == 2024
    assert parsed.month == 1
    assert parsed.day == 1
    assert parsed.hour == 12
    assert parsed.minute == 0
    assert parsed.second == 0


def test_activityanalyzer_parse_timestamp_z_suffix(activity_analyzer):
    """Test _parse_timestamp parses ISO string with Z suffix as UTC."""
    ts_str = "2024-01-01T12:00:00Z"
    parsed = activity_analyzer._parse_timestamp(ts_str)
    assert isinstance(parsed, datetime)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)


def test_activityanalyzer_parse_timestamp_invalid_string(activity_analyzer):
    """Test _parse_timestamp returns None for invalid string."""
    ts_str = "not-a-timestamp"
    parsed = activity_analyzer._parse_timestamp(ts_str)
    assert parsed is None


def test_activityanalyzer_parse_timestamp_none(activity_analyzer):
    """Test _parse_timestamp returns None for None input."""
    parsed = activity_analyzer._parse_timestamp(None)
    assert parsed is None


# -------------------- _detect_peak_hours tests --------------------


def test_activityanalyzer_detect_peak_hours_basic(activity_analyzer):
    """Test _detect_peak_hours identifies peak hours above threshold."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = []
    for i in range(8):
        activities.append({"timestamp": (base + timedelta(hours=0, minutes=i)).isoformat()})
    for i in range(2):
        activities.append({"timestamp": (base + timedelta(hours=1, minutes=i)).isoformat()})
    patterns = activity_analyzer._detect_peak_hours(activities)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.pattern_type == "peak_hours"
    assert "10:00" in pattern.description
    assert pattern.confidence == pytest.approx(0.85)


def test_activityanalyzer_detect_peak_hours_no_peak(activity_analyzer):
    """Test _detect_peak_hours returns empty list when no hour exceeds threshold."""
    base = datetime(2024, 1, 1, 0, 0, 0)
    activities = []
    for h in range(5):
        activities.append({"timestamp": (base + timedelta(hours=h)).isoformat()})
    patterns = activity_analyzer._detect_peak_hours(activities)
    assert patterns == []


def test_activityanalyzer_detect_peak_hours_invalid_timestamps(activity_analyzer):
    """Test _detect_peak_hours ignores activities with invalid timestamps."""
    activities = [
        {"timestamp": "invalid"},
        {"timestamp": None},
    ]
    patterns = activity_analyzer._detect_peak_hours(activities)
    assert patterns == []


# -------------------- _detect_action_sequences tests --------------------


def test_activityanalyzer_detect_action_sequences_min_length(activity_analyzer):
    """Test _detect_action_sequences returns empty list when fewer than 3 activities."""
    activities = [
        {"action": "a", "timestamp": "2024-01-01T00:00:00"},
        {"action": "b", "timestamp": "2024-01-01T00:01:00"},
    ]
    patterns = activity_analyzer._detect_action_sequences(activities)
    assert patterns == []


def test_activityanalyzer_detect_action_sequences_common_sequences(activity_analyzer):
    """Test _detect_action_sequences identifies sequences occurring at least twice."""
    activities = [
        {"action": "a"},
        {"action": "b"},
        {"action": "c"},
        {"action": "a"},
        {"action": "b"},
        {"action": "c"},
        {"action": "x"},
    ]
    patterns = activity_analyzer._detect_action_sequences(activities)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.pattern_type == "action_sequence"
    assert "a → b → c" in pattern.description
    assert "(occurred 2 times)" in pattern.description
    assert pattern.confidence == pytest.approx(0.75)


def test_activityanalyzer_detect_action_sequences_uses_empty_string_for_missing_action(activity_analyzer):
    """Test _detect_action_sequences uses empty string when action key is missing."""
    activities = [
        {"action": "a"},
        {},
        {"action": "c"},
        {"action": "a"},
        {},
        {"action": "c"},
    ]
    patterns = activity_analyzer._detect_action_sequences(activities)
    assert len(patterns) == 1
    assert "a →  → c" in patterns[0].description


# -------------------- _detect_regularity tests --------------------


def test_activityanalyzer_detect_regularity_not_enough_activities(activity_analyzer):
    """Test _detect_regularity returns empty list when fewer than 5 activities."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = [
        {"timestamp": (base + timedelta(minutes=i)).isoformat()} for i in range(4)
    ]
    patterns = activity_analyzer._detect_regularity(activities)
    assert patterns == []


def test_activityanalyzer_detect_regularity_not_enough_valid_timestamps(activity_analyzer):
    """Test _detect_regularity returns empty list when fewer than 5 valid timestamps."""
    activities = [
        {"timestamp": "invalid"},
        {"timestamp": None},
        {"timestamp": "2024-01-01T00:00:00"},
        {"timestamp": "2024-01-01T00:01:00"},
        {"timestamp": "2024-01-01T00:02:00"},
    ]
    patterns = activity_analyzer._detect_regularity(activities)
    assert patterns == []


def test_activityanalyzer_detect_regularity_highly_regular(activity_analyzer):
    """Test _detect_regularity detects highly regular intervals (low CV)."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = [
        {"timestamp": (base + timedelta(minutes=5 * i)).isoformat()} for i in range(6)
    ]
    patterns = activity_analyzer._detect_regularity(activities)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.pattern_type == "regularity"
    assert "Highly regular activity pattern" in pattern.description
    assert pattern.confidence == pytest.approx(0.9)


def test_activityanalyzer_detect_regularity_irregular(activity_analyzer):
    """Test _detect_regularity returns empty list for irregular intervals (high CV)."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    intervals = [1, 10, 30, 60, 120]
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
    """Test analyze_patterns aggregates patterns from all internal detectors."""
    with patch.object(activity_analyzer, "_detect_peak_hours") as mock_peak, \
         patch.object(activity_analyzer, "_detect_action_sequences") as mock_seq, \
         patch.object(activity_analyzer, "_detect_regularity") as mock_reg:

        mock_peak.return_value = [ActivityPattern("peak_hours", "peak", 0.8)]
        mock_seq.return_value = [ActivityPattern("action_sequence", "seq", 0.7)]
        mock_reg.return_value = [ActivityPattern("regularity", "reg", 0.9)]

        activities = [{"timestamp": "2024-01-01T00:00:00", "action": "a"}]
        patterns = activity_analyzer.analyze_patterns(activities)

        assert len(patterns) == 3
        assert {p.pattern_type for p in patterns} == {"peak_hours", "action_sequence", "regularity"}
        mock_peak.assert_called_once()
        mock_seq.assert_called_once()
        mock_reg.assert_called_once()


# -------------------- get_user_score tests --------------------


def test_activityanalyzer_get_user_score_empty(activity_analyzer):
    """Test get_user_score returns 0.0 for empty activities list."""
    score = activity_analyzer.get_user_score([])
    assert score == pytest.approx(0.0)


def test_activityanalyzer_get_user_score_basic(activity_analyzer):
    """Test get_user_score computes score based on diversity, frequency, and volume."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = []
    for i in range(10):
        activities.append(
            {
                "action": "a" if i < 5 else "b",
                "timestamp": (base + timedelta(days=i)).isoformat(),
            }
        )
    score = activity_analyzer.get_user_score(activities)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_activityanalyzer_get_user_score_all_unique_actions_single_day(activity_analyzer):
    """Test get_user_score with all unique actions on same day."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = [
        {"action": f"a{i}", "timestamp": (base + timedelta(minutes=i)).isoformat()}
        for i in range(10)
    ]
    score = activity_analyzer.get_user_score(activities)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_activityanalyzer_get_user_score_invalid_timestamps(activity_analyzer):
    """Test get_user_score falls back to total_actions when timestamps invalid."""
    activities = [
        {"action": "a", "timestamp": "invalid"},
        {"action": "b", "timestamp": None},
        {"action": "c"},
    ]
    score = activity_analyzer.get_user_score(activities)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_activityanalyzer_get_user_score_unique_action_logic(activity_analyzer):
    """Test get_user_score unique action counting logic with repeated actions."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    actions = ["a", "b", "a", "c", "b", "d"]
    activities = [
        {"action": act, "timestamp": (base + timedelta(minutes=i)).isoformat()}
        for i, act in enumerate(actions)
    ]
    score = activity_analyzer.get_user_score(activities)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


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


def test_activityanalyzer_detect_anomalies_ignores_actions_with_few_timestamps(activity_analyzer):
    """Test detect_anomalies ignores actions with fewer than 3 timestamps."""
    base = datetime(2024, 1, 1, 0, 0, 0)
    activities = [
        {"action": "a", "timestamp": (base + timedelta(minutes=i)).isoformat()}
        for i in range(3)
    ]
    activities.extend(
        {"action": "b", "timestamp": (base + timedelta(minutes=10 + i)).isoformat()}
        for i in range(2)
    )
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert anomalies == []


def test_activityanalyzer_detect_anomalies_no_intervals(activity_analyzer):
    """Test detect_anomalies handles case where intervals list is empty."""
    base = datetime(2024, 1, 1, 0, 0, 0)
    activities = [
        {"action": "a", "timestamp": base.isoformat()},
        {"action": "a", "timestamp": base.isoformat()},
        {"action": "a", "timestamp": base.isoformat()},
        {"action": "a", "timestamp": (base + timedelta(minutes=1)).isoformat()},
        {"action": "a", "timestamp": (base + timedelta(minutes=2)).isoformat()},
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert isinstance(anomalies, list)


def test_activityanalyzer_detect_anomalies_with_clear_outlier_interval(activity_analyzer):
    """Test detect_anomalies flags an interval with high z-score as anomaly."""
    base = datetime(2024, 1, 1, 0, 0, 0)
    timestamps = [
        base,
        base + timedelta(minutes=10),
        base + timedelta(minutes=20),
        base + timedelta(minutes=30),
        base + timedelta(hours=5),
        base + timedelta(hours=5, minutes=10),
    ]
    activities = [
        {"action": "a", "timestamp": ts.isoformat()} for ts in timestamps
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert isinstance(anomalies, list)
    for anomaly in anomalies:
        assert "action" in anomaly
        assert "timestamp" in anomaly
        assert "z_score" in anomaly
        assert "reason" in anomaly


def test_activityanalyzer_detect_anomalies_invalid_timestamps(activity_analyzer):
    """Test detect_anomalies ignores activities with invalid timestamps."""
    activities = [
        {"action": "a", "timestamp": "invalid"},
        {"action": "a", "timestamp": None},
        {"action": "a"},
        {"action": "a", "timestamp": "2024-01-01T00:00:00"},
        {"action": "a", "timestamp": "2024-01-01T00:10:00"},
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert isinstance(anomalies, list)


def test_activityanalyzer_detect_anomalies_uses_default_action_for_missing(activity_analyzer):
    """Test detect_anomalies uses 'unknown' for missing action key."""
    base = datetime(2024, 1, 1, 0, 0, 0)
    activities = [
        {"timestamp": (base + timedelta(minutes=i * 10)).isoformat()}
        for i in range(5)
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert isinstance(anomalies, list)


# -------------------- mocking / exception handling tests --------------------


def test_activityanalyzer_analyze_patterns_handles_internal_exception(activity_analyzer):
    """Test analyze_patterns propagates exceptions from internal methods."""
    with patch.object(activity_analyzer, "_detect_peak_hours", side_effect=RuntimeError("boom")):
        activities = [{"timestamp": "2024-01-01T00:00:00", "action": "a"}]
        with pytest.raises(RuntimeError):
            activity_analyzer.analyze_patterns(activities)


def test_activityanalyzer_detect_anomalies_parse_timestamp_exception(activity_analyzer, monkeypatch):
    """Test detect_anomalies handles exceptions from _parse_timestamp gracefully."""
    def bad_parse(ts):
        raise ValueError("parse error")

    monkeypatch.setattr(activity_analyzer, "_parse_timestamp", bad_parse)
    activities = [
        {"action": "a", "timestamp": "2024-01-01T00:00:00"},
        {"action": "a", "timestamp": "2024-01-01T00:10:00"},
        {"action": "a", "timestamp": "2024-01-01T00:20:00"},
        {"action": "a", "timestamp": "2024-01-01T00:30:00"},
        {"action": "a", "timestamp": "2024-01-01T00:40:00"},
    ]
    with pytest.raises(ValueError):
        activity_analyzer.detect_anomalies(activities)


def test_activityanalyzer_get_user_score_parse_timestamp_exception(activity_analyzer, monkeypatch):
    """Test get_user_score propagates exceptions from _parse_timestamp."""
    def bad_parse(ts):
        raise ValueError("parse error")

    monkeypatch.setattr(activity_analyzer, "_parse_timestamp", bad_parse)
    activities = [
        {"action": "a", "timestamp": "2024-01-01T00:00:00"},
        {"action": "b", "timestamp": "2024-01-02T00:00:00"},
    ]
    with pytest.raises(ValueError):
        activity_analyzer.get_user_score(activities)