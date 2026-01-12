import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone

from src.activity_analyzer import ActivityPattern, ActivityAnalyzer


@pytest.fixture
def activity_pattern_instance():
    """Create an ActivityPattern instance for testing."""
    return ActivityPattern(pattern_type="test_type", description="test_desc", confidence=0.75)


@pytest.fixture
def activity_analyzer_instance():
    """Create an ActivityAnalyzer instance for testing."""
    return ActivityAnalyzer()


def test_activitypattern_init_sets_attributes(activity_pattern_instance):
    """Test ActivityPattern __init__ correctly sets attributes."""
    assert activity_pattern_instance.pattern_type == "test_type"
    assert activity_pattern_instance.description == "test_desc"
    assert activity_pattern_instance.confidence == pytest.approx(0.75)


def test_activitypattern_to_dict_returns_expected_dict(activity_pattern_instance):
    """Test ActivityPattern.to_dict returns correct dictionary representation."""
    result = activity_pattern_instance.to_dict()
    assert result == {
        "pattern_type": "test_type",
        "description": "test_desc",
        "confidence": pytest.approx(0.75),
    }


def test_activityanalyzer_init_default_thresholds(activity_analyzer_instance):
    """Test ActivityAnalyzer __init__ sets default thresholds."""
    assert activity_analyzer_instance.peak_hour_threshold == pytest.approx(0.2)
    assert activity_analyzer_instance.anomaly_threshold == pytest.approx(3.0)


def test_activityanalyzer_analyze_patterns_empty_list(activity_analyzer_instance):
    """Test analyze_patterns returns empty list when no activities are provided."""
    result = activity_analyzer_instance.analyze_patterns([])
    assert result == []


def test_activityanalyzer_analyze_patterns_combines_all_detectors(activity_analyzer_instance):
    """Test analyze_patterns combines results from all internal detection methods."""
    activities = [{"timestamp": datetime.now(timezone.utc).isoformat(), "action": "a"}]

    with patch.object(activity_analyzer_instance, "_detect_peak_hours", return_value=[ActivityPattern("p", "peak", 0.8)]) as mock_peak, \
         patch.object(activity_analyzer_instance, "_detect_action_sequences", return_value=[ActivityPattern("s", "seq", 0.7)]) as mock_seq, \
         patch.object(activity_analyzer_instance, "_detect_regularity", return_value=[ActivityPattern("r", "reg", 0.9)]) as mock_reg:

        result = activity_analyzer_instance.analyze_patterns(activities)

        mock_peak.assert_called_once_with(activities)
        mock_seq.assert_called_once_with(activities)
        mock_reg.assert_called_once_with(activities)

        assert len(result) == 3
        assert [p.pattern_type for p in result] == ["p", "s", "r"]


def test_activityanalyzer_get_user_score_empty_list(activity_analyzer_instance):
    """Test get_user_score returns 0.0 when no activities are provided."""
    score = activity_analyzer_instance.get_user_score([])
    assert score == pytest.approx(0.0)


def test_activityanalyzer_get_user_score_basic_calculation(activity_analyzer_instance):
    """Test get_user_score calculates score based on diversity, frequency, and volume."""
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = [
        {"timestamp": (base_time + timedelta(days=i // 2)).isoformat(), "action": "a" if i < 3 else "b"}
        for i in range(6)
    ]
    score = activity_analyzer_instance.get_user_score(activities)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_activityanalyzer_get_user_score_no_timestamps(activity_analyzer_instance):
    """Test get_user_score when timestamps are missing or unparsable."""
    activities = [
        {"timestamp": "not-a-date", "action": "a"},
        {"timestamp": None, "action": "b"},
        {"action": "c"},
    ]
    score = activity_analyzer_instance.get_user_score(activities)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_activityanalyzer_get_user_score_unique_action_logic(activity_analyzer_instance):
    """Test get_user_score unique action counting logic with repeated actions."""
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = [
        {"timestamp": (base_time + timedelta(minutes=i)).isoformat(), "action": a}
        for i, a in enumerate(["a", "b", "a", "c", "b", "d"])
    ]
    score = activity_analyzer_instance.get_user_score(activities)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_activityanalyzer_detect_anomalies_too_few_activities(activity_analyzer_instance):
    """Test detect_anomalies returns empty list when fewer than 5 activities."""
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = [
        {"timestamp": (base_time + timedelta(minutes=i)).isoformat(), "action": "a"}
        for i in range(4)
    ]
    anomalies = activity_analyzer_instance.detect_anomalies(activities)
    assert anomalies == []


def test_activityanalyzer_detect_anomalies_no_anomalies(activity_analyzer_instance):
    """Test detect_anomalies returns empty list when intervals are regular."""
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = [
        {"timestamp": (base_time + timedelta(minutes=10 * i)).isoformat(), "action": "a"}
        for i in range(6)
    ]
    anomalies = activity_analyzer_instance.detect_anomalies(activities)
    assert anomalies == []


def test_activityanalyzer_detect_anomalies_detects_large_interval(activity_analyzer_instance):
    """Test detect_anomalies flags an interval with high z-score as anomaly."""
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    timestamps = [
        base_time,
        base_time + timedelta(minutes=10),
        base_time + timedelta(minutes=20),
        base_time + timedelta(minutes=30),
        base_time + timedelta(hours=5),
        base_time + timedelta(hours=5, minutes=10),
    ]
    activities = [{"timestamp": ts.isoformat(), "action": "a"} for ts in timestamps]
    anomalies = activity_analyzer_instance.detect_anomalies(activities)
    assert isinstance(anomalies, list)
    if anomalies:
        anomaly = anomalies[0]
        assert anomaly["action"] == "a"
        assert "timestamp" in anomaly
        assert "z_score" in anomaly
        assert isinstance(anomaly["z_score"], float)


def test_activityanalyzer_detect_anomalies_ignores_actions_with_few_timestamps(activity_analyzer_instance):
    """Test detect_anomalies ignores actions with fewer than 3 timestamps."""
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = [
        {"timestamp": (base_time + timedelta(minutes=i)).isoformat(), "action": "a"} for i in range(3)
    ] + [
        {"timestamp": (base_time + timedelta(minutes=100 + i)).isoformat(), "action": "b"} for i in range(2)
    ]
    anomalies = activity_analyzer_instance.detect_anomalies(activities)
    assert isinstance(anomalies, list)


def test_activityanalyzer_detect_anomalies_skips_unparsable_timestamps(activity_analyzer_instance):
    """Test detect_anomalies skips activities with unparsable timestamps."""
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = [
        {"timestamp": (base_time + timedelta(minutes=10 * i)).isoformat(), "action": "a"}
        for i in range(5)
    ]
    activities.append({"timestamp": "invalid", "action": "a"})
    anomalies = activity_analyzer_instance.detect_anomalies(activities)
    assert isinstance(anomalies, list)


def test_activityanalyzer_detect_peak_hours_no_timestamps(activity_analyzer_instance):
    """Test _detect_peak_hours returns empty list when no valid timestamps."""
    activities = [{"timestamp": "invalid", "action": "a"}]
    patterns = activity_analyzer_instance._detect_peak_hours(activities)
    assert patterns == []


def test_activityanalyzer_detect_peak_hours_identifies_peak(activity_analyzer_instance):
    """Test _detect_peak_hours identifies hours exceeding threshold."""
    base_time = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    activities = []
    for i in range(8):
        activities.append({"timestamp": (base_time + timedelta(minutes=i)).isoformat(), "action": "a"})
    for i in range(2):
        activities.append({"timestamp": (base_time.replace(hour=5) + timedelta(minutes=i)).isoformat(), "action": "b"})
    patterns = activity_analyzer_instance._detect_peak_hours(activities)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.pattern_type == "peak_hours"
    assert "High activity during hours" in pattern.description
    assert pattern.confidence == pytest.approx(0.85)


def test_activityanalyzer_detect_action_sequences_too_few(activity_analyzer_instance):
    """Test _detect_action_sequences returns empty list when fewer than 3 activities."""
    activities = [
        {"timestamp": datetime.now(timezone.utc).isoformat(), "action": "a"},
        {"timestamp": datetime.now(timezone.utc).isoformat(), "action": "b"},
    ]
    patterns = activity_analyzer_instance._detect_action_sequences(activities)
    assert patterns == []


def test_activityanalyzer_detect_action_sequences_common_sequence(activity_analyzer_instance):
    """Test _detect_action_sequences identifies common sequences occurring at least twice."""
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    actions = ["a", "b", "c", "a", "b", "c", "d", "e", "f"]
    activities = [
        {"timestamp": (base_time + timedelta(minutes=i)).isoformat(), "action": act}
        for i, act in enumerate(actions)
    ]
    patterns = activity_analyzer_instance._detect_action_sequences(activities)
    assert patterns
    seq_descriptions = [p.description for p in patterns]
    assert any("a → b → c" in desc for desc in seq_descriptions)
    for p in patterns:
        assert p.pattern_type == "action_sequence"
        assert p.confidence == pytest.approx(0.75)


def test_activityanalyzer_detect_action_sequences_limits_to_top_three(activity_analyzer_instance):
    """Test _detect_action_sequences returns at most three patterns."""
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    seqs = [
        ["a", "b", "c"],
        ["d", "e", "f"],
        ["g", "h", "i"],
        ["a", "b", "c"],
        ["d", "e", "f"],
        ["g", "h", "i"],
        ["a", "b", "c"],
    ]
    activities = []
    minute = 0
    for seq in seqs:
        for act in seq:
            activities.append(
                {"timestamp": (base_time + timedelta(minutes=minute)).isoformat(), "action": act}
            )
            minute += 1
    patterns = activity_analyzer_instance._detect_action_sequences(activities)
    assert len(patterns) <= 3


def test_activityanalyzer_detect_regularity_too_few_activities(activity_analyzer_instance):
    """Test _detect_regularity returns empty list when fewer than 5 activities."""
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = [
        {"timestamp": (base_time + timedelta(minutes=i)).isoformat(), "action": "a"}
        for i in range(4)
    ]
    patterns = activity_analyzer_instance._detect_regularity(activities)
    assert patterns == []


def test_activityanalyzer_detect_regularity_insufficient_valid_timestamps(activity_analyzer_instance):
    """Test _detect_regularity returns empty list when fewer than 5 valid timestamps."""
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = [
        {"timestamp": (base_time + timedelta(minutes=i)).isoformat(), "action": "a"}
        for i in range(4)
    ]
    activities.append({"timestamp": "invalid", "action": "a"})
    patterns = activity_analyzer_instance._detect_regularity(activities)
    assert patterns == []


def test_activityanalyzer_detect_regularity_highly_regular(activity_analyzer_instance):
    """Test _detect_regularity detects highly regular activity pattern."""
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = [
        {"timestamp": (base_time + timedelta(minutes=10 * i)).isoformat(), "action": "a"}
        for i in range(6)
    ]
    patterns = activity_analyzer_instance._detect_regularity(activities)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.pattern_type == "regularity"
    assert "Highly regular activity pattern" in pattern.description
    assert pattern.confidence == pytest.approx(0.9)


def test_activityanalyzer_detect_regularity_irregular(activity_analyzer_instance):
    """Test _detect_regularity returns empty list for irregular intervals."""
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    intervals = [1, 5, 20, 2, 30]
    timestamps = [base_time]
    for minutes in intervals:
        timestamps.append(timestamps[-1] + timedelta(minutes=minutes))
    activities = [{"timestamp": ts.isoformat(), "action": "a"} for ts in timestamps]
    patterns = activity_analyzer_instance._detect_regularity(activities)
    assert patterns == []


def test_activityanalyzer_parse_timestamp_with_datetime(activity_analyzer_instance):
    """Test _parse_timestamp returns datetime unchanged when input is datetime."""
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    result = activity_analyzer_instance._parse_timestamp(ts)
    assert isinstance(result, datetime)
    assert result == ts


def test_activityanalyzer_parse_timestamp_with_iso_string(activity_analyzer_instance):
    """Test _parse_timestamp parses ISO 8601 string correctly."""
    ts = "2024-01-01T12:34:56+00:00"
    result = activity_analyzer_instance._parse_timestamp(ts)
    assert isinstance(result, datetime)
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 1
    assert result.hour == 12
    assert result.minute == 34
    assert result.second == 56


def test_activityanalyzer_parse_timestamp_with_z_suffix(activity_analyzer_instance):
    """Test _parse_timestamp parses ISO 8601 string with Z suffix."""
    ts = "2024-01-01T12:34:56Z"
    result = activity_analyzer_instance._parse_timestamp(ts)
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


def test_activityanalyzer_parse_timestamp_invalid_string(activity_analyzer_instance):
    """Test _parse_timestamp returns None for invalid string."""
    ts = "not-a-timestamp"
    result = activity_analyzer_instance._parse_timestamp(ts)
    assert result is None


def test_activityanalyzer_parse_timestamp_unsupported_type(activity_analyzer_instance):
    """Test _parse_timestamp returns None for unsupported type."""
    result = activity_analyzer_instance._parse_timestamp(12345)
    assert result is None


def test_activityanalyzer_detect_anomalies_exception_handling_in_parse(activity_analyzer_instance, monkeypatch):
    """Test detect_anomalies handles exceptions from _parse_timestamp gracefully."""
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = [
        {"timestamp": (base_time + timedelta(minutes=10 * i)).isoformat(), "action": "a"}
        for i in range(6)
    ]

    def bad_parse(ts):
        raise ValueError("parse error")

    monkeypatch.setattr(activity_analyzer_instance, "_parse_timestamp", bad_parse)
    anomalies = activity_analyzer_instance.detect_anomalies(activities)
    assert anomalies == []


def test_activityanalyzer_get_user_score_exception_in_parse(activity_analyzer_instance, monkeypatch):
    """Test get_user_score handles exceptions from _parse_timestamp gracefully."""
    activities = [
        {"timestamp": "2024-01-01T00:00:00Z", "action": "a"},
        {"timestamp": "2024-01-02T00:00:00Z", "action": "b"},
    ]

    def bad_parse(ts):
        raise ValueError("parse error")

    monkeypatch.setattr(activity_analyzer_instance, "_parse_timestamp", bad_parse)
    score = activity_analyzer_instance.get_user_score(activities)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_activityanalyzer_detect_peak_hours_exception_in_parse(activity_analyzer_instance, monkeypatch):
    """Test _detect_peak_hours handles exceptions from _parse_timestamp gracefully."""
    activities = [{"timestamp": "2024-01-01T00:00:00Z", "action": "a"}]

    def bad_parse(ts):
        raise ValueError("parse error")

    monkeypatch.setattr(activity_analyzer_instance, "_parse_timestamp", bad_parse)
    patterns = activity_analyzer_instance._detect_peak_hours(activities)
    assert patterns == []


def test_activityanalyzer_detect_regularity_exception_in_parse(activity_analyzer_instance, monkeypatch):
    """Test _detect_regularity handles exceptions from _parse_timestamp gracefully."""
    activities = [{"timestamp": "2024-01-01T00:00:00Z", "action": "a"} for _ in range(6)]

    def bad_parse(ts):
        raise ValueError("parse error")

    monkeypatch.setattr(activity_analyzer_instance, "_parse_timestamp", bad_parse)
    patterns = activity_analyzer_instance._detect_regularity(activities)
    assert patterns == []


def test_activityanalyzer_analyze_patterns_with_mixed_results(activity_analyzer_instance, monkeypatch):
    """Test analyze_patterns returns combined patterns from detectors with mixed outputs."""
    activities = [{"timestamp": "2024-01-01T00:00:00Z", "action": "a"}]

    monkeypatch.setattr(
        activity_analyzer_instance,
        "_detect_peak_hours",
        MagicMock(return_value=[ActivityPattern("peak_hours", "desc1", 0.5)]),
    )
    monkeypatch.setattr(
        activity_analyzer_instance,
        "_detect_action_sequences",
        MagicMock(return_value=[]),
    )
    monkeypatch.setattr(
        activity_analyzer_instance,
        "_detect_regularity",
        MagicMock(return_value=[ActivityPattern("regularity", "desc2", 0.9)]),
    )

    patterns = activity_analyzer_instance.analyze_patterns(activities)
    assert len(patterns) == 2
    types = {p.pattern_type for p in patterns}
    assert types == {"peak_hours", "regularity"}