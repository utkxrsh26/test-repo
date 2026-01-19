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
    pattern = ActivityPattern(pattern_type="type1", description="desc1", confidence=0.5)
    assert pattern.pattern_type == "type1"
    assert pattern.description == "desc1"
    assert pattern.confidence == pytest.approx(0.5)


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


def test_activityanalyzer_parse_timestamp_datetime(activity_analyzer_instance):
    """Test _parse_timestamp with datetime input returns same datetime."""
    ts = datetime(2024, 1, 1, 12, 0, 0)
    parsed = activity_analyzer_instance._parse_timestamp(ts)
    assert parsed == ts


def test_activityanalyzer_parse_timestamp_iso_string(activity_analyzer_instance):
    """Test _parse_timestamp with ISO string returns correct datetime."""
    ts_str = "2024-01-01T12:00:00"
    parsed = activity_analyzer_instance._parse_timestamp(ts_str)
    assert isinstance(parsed, datetime)
    assert parsed.year == 2024
    assert parsed.month == 1
    assert parsed.day == 1
    assert parsed.hour == 12
    assert parsed.minute == 0
    assert parsed.second == 0


def test_activityanalyzer_parse_timestamp_z_suffix(activity_analyzer_instance):
    """Test _parse_timestamp with Z suffix string is handled correctly."""
    ts_str = "2024-01-01T12:00:00Z"
    parsed = activity_analyzer_instance._parse_timestamp(ts_str)
    assert isinstance(parsed, datetime)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)


def test_activityanalyzer_parse_timestamp_invalid_string(activity_analyzer_instance):
    """Test _parse_timestamp with invalid string returns None."""
    ts_str = "not-a-timestamp"
    parsed = activity_analyzer_instance._parse_timestamp(ts_str)
    assert parsed is None


def test_activityanalyzer_parse_timestamp_unsupported_type(activity_analyzer_instance):
    """Test _parse_timestamp with unsupported type returns None."""
    parsed = activity_analyzer_instance._parse_timestamp(12345)
    assert parsed is None


def test_activityanalyzer_analyze_patterns_empty(activity_analyzer_instance):
    """Test analyze_patterns returns empty list for no activities."""
    result = activity_analyzer_instance.analyze_patterns([])
    assert result == []


def test_activityanalyzer_analyze_patterns_calls_internal_methods(activity_analyzer_instance):
    """Test analyze_patterns orchestrates internal detection methods."""
    activities = [{"timestamp": datetime(2024, 1, 1, 10, 0), "action": "a"}]

    with patch.object(activity_analyzer_instance, "_detect_peak_hours", return_value=[ActivityPattern("p", "d", 0.1)]) as mock_peak, \
         patch.object(activity_analyzer_instance, "_detect_action_sequences", return_value=[ActivityPattern("s", "d2", 0.2)]) as mock_seq, \
         patch.object(activity_analyzer_instance, "_detect_regularity", return_value=[ActivityPattern("r", "d3", 0.3)]) as mock_reg:

        result = activity_analyzer_instance.analyze_patterns(activities)

        mock_peak.assert_called_once_with(activities)
        mock_seq.assert_called_once_with(activities)
        mock_reg.assert_called_once_with(activities)

        assert len(result) == 3
        assert {p.pattern_type for p in result} == {"p", "s", "r"}


def test_activityanalyzer_get_user_score_empty(activity_analyzer_instance):
    """Test get_user_score returns 0.0 for empty activities."""
    score = activity_analyzer_instance.get_user_score([])
    assert score == pytest.approx(0.0)


def test_activityanalyzer_get_user_score_basic(activity_analyzer_instance):
    """Test get_user_score computes expected score for simple case."""
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    activities = [
        {"timestamp": base.isoformat(), "action": "a"},
        {"timestamp": (base + timedelta(hours=1)).isoformat(), "action": "b"},
        {"timestamp": (base + timedelta(hours=2)).isoformat(), "action": "a"},
        {"timestamp": (base + timedelta(hours=3)).isoformat(), "action": "c"},
    ]
    # total_actions = 4
    # unique_actions = 3 (a, b, c)
    # days_active = 1
    # actions_per_day = 4
    # diversity_score = 3/4 = 0.75
    # frequency_score = min(4/10, 1) = 0.4
    # volume_score = min(4/100, 1) = 0.04
    # final = (0.75*0.3 + 0.4*0.4 + 0.04*0.3)*100
    expected = (0.75 * 0.3 + 0.4 * 0.4 + 0.04 * 0.3) * 100
    score = activity_analyzer_instance.get_user_score(activities)
    assert score == pytest.approx(round(expected, 2))


def test_activityanalyzer_get_user_score_no_timestamps(activity_analyzer_instance):
    """Test get_user_score when timestamps are missing uses total_actions as actions_per_day."""
    activities = [
        {"action": "a"},
        {"action": "b"},
        {"action": "c"},
    ]
    # total_actions = 3
    # unique_actions = 3
    # actions_per_day = 3
    # diversity_score = 1.0
    # frequency_score = 0.3
    # volume_score = 0.03
    expected = (1.0 * 0.3 + 0.3 * 0.4 + 0.03 * 0.3) * 100
    score = activity_analyzer_instance.get_user_score(activities)
    assert score == pytest.approx(round(expected, 2))


def test_activityanalyzer_get_user_score_duplicate_actions(activity_analyzer_instance):
    """Test get_user_score unique action counting logic with duplicates."""
    base = datetime(2024, 1, 1, 10, 0)
    activities = [
        {"timestamp": base, "action": "a"},
        {"timestamp": base + timedelta(hours=1), "action": "a"},
        {"timestamp": base + timedelta(hours=2), "action": "a"},
    ]
    # total_actions = 3
    # unique_actions = 1 (due to naive algorithm)
    # days_active = 1
    # actions_per_day = 3
    # diversity_score = 1/3
    # frequency_score = 0.3
    # volume_score = 0.03
    diversity = 1 / 3
    expected = (diversity * 0.3 + 0.3 * 0.4 + 0.03 * 0.3) * 100
    score = activity_analyzer_instance.get_user_score(activities)
    assert score == pytest.approx(round(expected, 2))


def test_activityanalyzer_detect_anomalies_too_few(activity_analyzer_instance):
    """Test detect_anomalies returns empty list when fewer than 5 activities."""
    activities = [{"timestamp": datetime(2024, 1, 1, 10, 0), "action": "a"}] * 4
    result = activity_analyzer_instance.detect_anomalies(activities)
    assert result == []


def test_activityanalyzer_detect_anomalies_no_intervals(activity_analyzer_instance):
    """Test detect_anomalies when all timestamps fail parsing results in no anomalies."""
    activities = [
        {"timestamp": "invalid", "action": "a"},
        {"timestamp": "invalid", "action": "a"},
        {"timestamp": "invalid", "action": "a"},
        {"timestamp": "invalid", "action": "a"},
        {"timestamp": "invalid", "action": "a"},
    ]
    result = activity_analyzer_instance.detect_anomalies(activities)
    assert result == []


def test_activityanalyzer_detect_anomalies_basic(activity_analyzer_instance):
    """Test detect_anomalies identifies anomalies based on z-score threshold."""
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    # Create mostly regular intervals of 60s, with one large gap
    timestamps = [
        base,
        base + timedelta(seconds=60),
        base + timedelta(seconds=120),
        base + timedelta(seconds=180),
        base + timedelta(seconds=600),  # large interval from previous
        base + timedelta(seconds=660),
    ]
    activities = [{"timestamp": ts.isoformat(), "action": "click"} for ts in timestamps]

    anomalies = activity_analyzer_instance.detect_anomalies(activities)

    assert isinstance(anomalies, list)
    # Depending on statistics, at least one anomaly should be detected
    assert len(anomalies) >= 1
    for anomaly in anomalies:
        assert anomaly["action"] == "click"
        assert "timestamp" in anomaly
        assert "z_score" in anomaly
        assert isinstance(anomaly["z_score"], float)
        assert "reason" in anomaly


def test_activityanalyzer_detect_anomalies_multiple_actions(activity_analyzer_instance):
    """Test detect_anomalies handles multiple actions and skips those with <3 timestamps."""
    base = datetime(2024, 1, 1, 10, 0)
    activities = [
        {"timestamp": base + timedelta(minutes=i), "action": "a"} for i in range(6)
    ] + [
        {"timestamp": base + timedelta(minutes=i), "action": "b"} for i in range(2)
    ]
    anomalies = activity_analyzer_instance.detect_anomalies(activities)
    # Action 'b' has only 2 timestamps, should be ignored
    for anomaly in anomalies:
        assert anomaly["action"] == "a"


def test_activityanalyzer_detect_peak_hours_no_valid_timestamps(activity_analyzer_instance):
    """Test _detect_peak_hours returns empty when no valid timestamps."""
    activities = [{"timestamp": "invalid", "action": "a"} for _ in range(5)]
    result = activity_analyzer_instance._detect_peak_hours(activities)
    assert result == []


def test_activityanalyzer_detect_peak_hours_threshold(activity_analyzer_instance):
    """Test _detect_peak_hours identifies hours exceeding threshold."""
    base = datetime(2024, 1, 1, 10, 0)
    activities = []
    # 8 activities at 10:00
    for _ in range(8):
        activities.append({"timestamp": base, "action": "a"})
    # 2 activities at 11:00
    for _ in range(2):
        activities.append({"timestamp": base.replace(hour=11), "action": "b"})

    # total = 10, hour 10 has 0.8 > 0.2, hour 11 has 0.2 == threshold (not strictly >)
    patterns = activity_analyzer_instance._detect_peak_hours(activities)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.pattern_type == "peak_hours"
    assert "10:00" in pattern.description
    assert "11:00" not in pattern.description
    assert pattern.confidence == pytest.approx(0.85)


def test_activityanalyzer_detect_action_sequences_too_short(activity_analyzer_instance):
    """Test _detect_action_sequences returns empty when fewer than 3 activities."""
    activities = [
        {"timestamp": datetime(2024, 1, 1, 10, 0), "action": "a"},
        {"timestamp": datetime(2024, 1, 1, 10, 1), "action": "b"},
    ]
    result = activity_analyzer_instance._detect_action_sequences(activities)
    assert result == []


def test_activityanalyzer_detect_action_sequences_common_sequences(activity_analyzer_instance):
    """Test _detect_action_sequences identifies common sequences occurring at least twice."""
    base = datetime(2024, 1, 1, 10, 0)
    activities = [
        {"timestamp": base + timedelta(minutes=i), "action": a}
        for i, a in enumerate(
            [
                "a",
                "b",
                "c",  # seq1: a,b,c
                "a",
                "b",
                "c",  # seq2: a,b,c
                "x",
                "y",
                "z",
            ]
        )
    ]
    patterns = activity_analyzer_instance._detect_action_sequences(activities)
    assert len(patterns) >= 1
    descriptions = [p.description for p in patterns]
    assert any("a → b → c" in d for d in descriptions)
    for p in patterns:
        assert p.pattern_type == "action_sequence"
        assert p.confidence == pytest.approx(0.75)


def test_activityanalyzer_detect_action_sequences_top3_limit(activity_analyzer_instance):
    """Test _detect_action_sequences returns at most 3 most common sequences."""
    base = datetime(2024, 1, 1, 10, 0)
    actions = ["a", "b", "c", "d", "e", "f", "g"]
    activities = []
    # Create multiple repeating sequences
    for offset in range(5):
        for seq in [("a", "b", "c"), ("b", "c", "d"), ("c", "d", "e"), ("d", "e", "f")]:
            for i, act in enumerate(seq):
                activities.append(
                    {"timestamp": base + timedelta(minutes=len(activities)), "action": act}
                )
    patterns = activity_analyzer_instance._detect_action_sequences(activities)
    assert len(patterns) <= 3


def test_activityanalyzer_detect_regularity_too_few(activity_analyzer_instance):
    """Test _detect_regularity returns empty when fewer than 5 activities."""
    activities = [
        {"timestamp": datetime(2024, 1, 1, 10, i), "action": "a"} for i in range(4)
    ]
    result = activity_analyzer_instance._detect_regularity(activities)
    assert result == []


def test_activityanalyzer_detect_regularity_insufficient_valid_timestamps(activity_analyzer_instance):
    """Test _detect_regularity returns empty when fewer than 5 valid timestamps."""
    activities = [
        {"timestamp": "invalid", "action": "a"} for _ in range(5)
    ]
    result = activity_analyzer_instance._detect_regularity(activities)
    assert result == []


def test_activityanalyzer_detect_regularity_highly_regular(activity_analyzer_instance):
    """Test _detect_regularity detects highly regular intervals with low CV."""
    base = datetime(2024, 1, 1, 10, 0)
    # Perfect 60-second intervals
    activities = [
        {"timestamp": base + timedelta(seconds=60 * i), "action": "a"} for i in range(6)
    ]
    patterns = activity_analyzer_instance._detect_regularity(activities)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.pattern_type == "regularity"
    assert "CV:" in pattern.description
    assert pattern.confidence == pytest.approx(0.9)


def test_activityanalyzer_detect_regularity_irregular(activity_analyzer_instance):
    """Test _detect_regularity returns empty for irregular intervals with high CV."""
    base = datetime(2024, 1, 1, 10, 0)
    intervals = [10, 100, 30, 300, 20, 400]
    timestamps = [base]
    for sec in intervals:
        timestamps.append(timestamps[-1] + timedelta(seconds=sec))
    activities = [{"timestamp": ts, "action": "a"} for ts in timestamps]
    patterns = activity_analyzer_instance._detect_regularity(activities)
    assert patterns == []


def test_activityanalyzer_analyze_patterns_integration(activity_analyzer_instance):
    """Test analyze_patterns end-to-end with realistic activities."""
    base = datetime(2024, 1, 1, 8, 0)
    activities = []
    # Peak hours around 9-10
    for i in range(10):
        activities.append({"timestamp": base.replace(hour=9) + timedelta(minutes=i), "action": "login"})
    # Some sequences and regularity
    for i in range(6):
        activities.append({"timestamp": base + timedelta(hours=2, minutes=10 * i), "action": "view"})
        activities.append({"timestamp": base + timedelta(hours=2, minutes=10 * i + 1), "action": "click"})
        activities.append({"timestamp": base + timedelta(hours=2, minutes=10 * i + 2), "action": "logout"})

    patterns = activity_analyzer_instance.analyze_patterns(activities)
    assert isinstance(patterns, list)
    assert len(patterns) >= 1
    types = {p.pattern_type for p in patterns}
    assert "peak_hours" in types
    assert "action_sequence" in types or "regularity" in types


def test_activityanalyzer_detect_anomalies_exception_handling(activity_analyzer_instance):
    """Test detect_anomalies handles exceptions from _parse_timestamp gracefully."""
    base = datetime(2024, 1, 1, 10, 0)
    activities = [
        {"timestamp": base + timedelta(minutes=i), "action": "a"} for i in range(6)
    ]

    with patch.object(activity_analyzer_instance, "_parse_timestamp", side_effect=Exception("parse error")):
        # Should not raise, but return empty anomalies due to failure to parse
        result = activity_analyzer_instance.detect_anomalies(activities)
        assert result == []


def test_activityanalyzer_get_user_score_exception_handling(activity_analyzer_instance):
    """Test get_user_score handles exceptions from _parse_timestamp gracefully."""
    activities = [
        {"timestamp": "2024-01-01T10:00:00Z", "action": "a"},
        {"timestamp": "2024-01-01T11:00:00Z", "action": "b"},
    ]

    with patch.object(activity_analyzer_instance, "_parse_timestamp", side_effect=Exception("parse error")):
        # When parsing fails, actions_per_day should fall back to total_actions
        score = activity_analyzer_instance.get_user_score(activities)
        assert isinstance(score, float)