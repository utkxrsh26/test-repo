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
        {"timestamp": (base + timedelta(minutes=0)).isoformat(), "action": "login"},
        {"timestamp": (base + timedelta(minutes=5)).isoformat(), "action": "view"},
        {"timestamp": (base + timedelta(minutes=10)).isoformat(), "action": "click"},
        {"timestamp": (base + timedelta(minutes=15)).isoformat(), "action": "logout"},
        {"timestamp": (base + timedelta(minutes=20)).isoformat(), "action": "login"},
    ]


# -----------------------
# ActivityPattern tests
# -----------------------


def test_activitypattern_init_and_attributes():
    """Test ActivityPattern initialization and attribute assignment."""
    pattern = ActivityPattern("type1", "desc", 0.9)
    assert pattern.pattern_type == "type1"
    assert pattern.description == "desc"
    assert pattern.confidence == pytest.approx(0.9)


def test_activitypattern_to_dict():
    """Test ActivityPattern.to_dict returns correct dictionary."""
    pattern = ActivityPattern("peak_hours", "High activity", 0.85)
    result = pattern.to_dict()
    assert result["pattern_type"] == "peak_hours"
    assert result["description"] == "High activity"
    assert result["confidence"] == pytest.approx(0.85)


# -----------------------
# ActivityAnalyzer.__init__
# -----------------------


def test_activityanalyzer_init_defaults(activity_analyzer):
    """Test ActivityAnalyzer initialization sets default thresholds."""
    assert activity_analyzer.peak_hour_threshold == pytest.approx(0.2)
    assert activity_analyzer.anomaly_threshold == pytest.approx(3.0)


# -----------------------
# _parse_timestamp tests
# -----------------------


def test_activityanalyzer_parse_timestamp_datetime(activity_analyzer):
    """Test _parse_timestamp returns datetime unchanged when given datetime."""
    ts = datetime(2024, 1, 1, 12, 0, 0)
    parsed = activity_analyzer._parse_timestamp(ts)
    assert parsed == ts


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


# -----------------------
# _detect_peak_hours tests
# -----------------------


def test_activityanalyzer_detect_peak_hours_basic(activity_analyzer):
    """Test _detect_peak_hours identifies peak hours above threshold."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = []
    # 8 actions at 10:00, 2 actions at 11:00 -> 10:00 is 0.8 of total
    for i in range(8):
        activities.append({"timestamp": (base + timedelta(minutes=i)).isoformat(), "action": "a"})
    for i in range(2):
        activities.append({"timestamp": (base + timedelta(hours=1, minutes=i)).isoformat(), "action": "b"})

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
    # 5 hours with equal counts -> each 0.2, threshold is > 0.2 so none
    for h in range(5):
        activities.append({"timestamp": (base.replace(hour=h)).isoformat(), "action": "a"})
    patterns = activity_analyzer._detect_peak_hours(activities)
    assert patterns == []


def test_activityanalyzer_detect_peak_hours_no_valid_timestamps(activity_analyzer):
    """Test _detect_peak_hours returns empty when timestamps are invalid."""
    activities = [{"timestamp": "invalid", "action": "a"} for _ in range(5)]
    patterns = activity_analyzer._detect_peak_hours(activities)
    assert patterns == []


# -----------------------
# _detect_action_sequences tests
# -----------------------


def test_activityanalyzer_detect_action_sequences_min_length(activity_analyzer):
    """Test _detect_action_sequences returns empty when fewer than 3 activities."""
    activities = [
        {"timestamp": "2024-01-01T10:00:00Z", "action": "a"},
        {"timestamp": "2024-01-01T10:01:00Z", "action": "b"},
    ]
    patterns = activity_analyzer._detect_action_sequences(activities)
    assert patterns == []


def test_activityanalyzer_detect_action_sequences_common_sequences(activity_analyzer):
    """Test _detect_action_sequences identifies repeated 3-action sequences."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    # Sequence: login -> view -> click appears 3 times
    actions = [
        "login", "view", "click",
        "logout",
        "login", "view", "click",
        "login", "view", "click",
    ]
    activities = [
        {"timestamp": (base + timedelta(minutes=i)).isoformat(), "action": act}
        for i, act in enumerate(actions)
    ]
    patterns = activity_analyzer._detect_action_sequences(activities)
    assert len(patterns) >= 1
    seq_pattern = patterns[0]
    assert seq_pattern.pattern_type == "action_sequence"
    assert "login → view → click" in seq_pattern.description
    assert "occurred 3 times" in seq_pattern.description
    assert seq_pattern.confidence == pytest.approx(0.75)


def test_activityanalyzer_detect_action_sequences_threshold_count(activity_analyzer):
    """Test _detect_action_sequences only returns sequences with count >= 2."""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    # Only one occurrence of each 3-length sequence
    actions = ["a", "b", "c", "d", "e"]
    activities = [
        {"timestamp": (base + timedelta(minutes=i)).isoformat(), "action": act}
        for i, act in enumerate(actions)
    ]
    patterns = activity_analyzer._detect_action_sequences(activities)
    assert patterns == []


# -----------------------
# _detect_regularity tests
# -----------------------


def test_activityanalyzer_detect_regularity_not_enough_activities(activity_analyzer):
    """Test _detect_regularity returns empty when fewer than 5 activities."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = [
        {"timestamp": (base + timedelta(minutes=i)).isoformat(), "action": "a"}
        for i in range(4)
    ]
    patterns = activity_analyzer._detect_regularity(activities)
    assert patterns == []


def test_activityanalyzer_detect_regularity_highly_regular(activity_analyzer):
    """Test _detect_regularity detects highly regular intervals (low CV)."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    # Exactly 10-minute intervals
    activities = [
        {"timestamp": (base + timedelta(minutes=10 * i)).isoformat(), "action": "a"}
        for i in range(6)
    ]
    patterns = activity_analyzer._detect_regularity(activities)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.pattern_type == "regularity"
    assert "Highly regular activity pattern" in pattern.description
    assert pattern.confidence == pytest.approx(0.9)


def test_activityanalyzer_detect_regularity_irregular(activity_analyzer):
    """Test _detect_regularity returns empty for irregular intervals (high CV)."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    # Irregular intervals
    offsets = [0, 1, 5, 20, 60, 61]
    activities = [
        {"timestamp": (base + timedelta(minutes=o)).isoformat(), "action": "a"}
        for o in offsets
    ]
    patterns = activity_analyzer._detect_regularity(activities)
    assert patterns == []


def test_activityanalyzer_detect_regularity_invalid_timestamps(activity_analyzer):
    """Test _detect_regularity ignores invalid timestamps and may return empty."""
    activities = [
        {"timestamp": "invalid", "action": "a"} for _ in range(10)
    ]
    patterns = activity_analyzer._detect_regularity(activities)
    assert patterns == []


# -----------------------
# analyze_patterns tests
# -----------------------


def test_activityanalyzer_analyze_patterns_empty(activity_analyzer):
    """Test analyze_patterns returns empty list for no activities."""
    patterns = activity_analyzer.analyze_patterns([])
    assert patterns == []


def test_activityanalyzer_analyze_patterns_combines_detectors(activity_analyzer, sample_activities):
    """Test analyze_patterns aggregates patterns from all detectors."""
    with patch.object(ActivityAnalyzer, "_detect_peak_hours", return_value=[ActivityPattern("peak_hours", "desc1", 0.8)]) as mock_peak, \
         patch.object(ActivityAnalyzer, "_detect_action_sequences", return_value=[ActivityPattern("action_sequence", "desc2", 0.7)]) as mock_seq, \
         patch.object(ActivityAnalyzer, "_detect_regularity", return_value=[ActivityPattern("regularity", "desc3", 0.9)]) as mock_reg:

        patterns = activity_analyzer.analyze_patterns(sample_activities)

        mock_peak.assert_called_once()
        mock_seq.assert_called_once()
        mock_reg.assert_called_once()

        assert len(patterns) == 3
        types = {p.pattern_type for p in patterns}
        assert types == {"peak_hours", "action_sequence", "regularity"}


# -----------------------
# get_user_score tests
# -----------------------


def test_activityanalyzer_get_user_score_empty(activity_analyzer):
    """Test get_user_score returns 0.0 for empty activities."""
    score = activity_analyzer.get_user_score([])
    assert score == pytest.approx(0.0)


def test_activityanalyzer_get_user_score_basic(activity_analyzer):
    """Test get_user_score computes score based on diversity, frequency, and volume."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = []
    # 10 actions over 2 days, 3 unique actions
    actions = ["a", "b", "c", "a", "b", "c", "a", "a", "b", "c"]
    for i, act in enumerate(actions):
        ts = base + timedelta(hours=i * 5)
        activities.append({"timestamp": ts.isoformat(), "action": act})

    score = activity_analyzer.get_user_score(activities)

    # Manually compute expected score according to implementation
    total_actions = 10
    unique_actions = 3
    first_ts = activities[0]["timestamp"]
    last_ts = activities[-1]["timestamp"]
    first_dt = datetime.fromisoformat(first_ts)
    last_dt = datetime.fromisoformat(last_ts)
    days_active = max((last_dt - first_dt).days, 1)
    actions_per_day = total_actions / days_active
    diversity_score = unique_actions / total_actions
    frequency_score = min(actions_per_day / 10.0, 1.0)
    volume_score = min(total_actions / 100.0, 1.0)
    expected = (diversity_score * 0.3 + frequency_score * 0.4 + volume_score * 0.3) * 100

    assert score == pytest.approx(round(expected, 2))


def test_activityanalyzer_get_user_score_no_valid_timestamps(activity_analyzer):
    """Test get_user_score falls back to total_actions when timestamps invalid."""
    activities = [
        {"timestamp": "invalid", "action": "a"},
        {"timestamp": "invalid", "action": "b"},
        {"timestamp": "invalid", "action": "a"},
    ]
    score = activity_analyzer.get_user_score(activities)

    total_actions = 3
    unique_actions = 2  # 'a', 'b'
    actions_per_day = total_actions
    diversity_score = unique_actions / total_actions
    frequency_score = min(actions_per_day / 10.0, 1.0)
    volume_score = min(total_actions / 100.0, 1.0)
    expected = (diversity_score * 0.3 + frequency_score * 0.4 + volume_score * 0.3) * 100

    assert score == pytest.approx(round(expected, 2))


def test_activityanalyzer_get_user_score_unique_action_logic(activity_analyzer):
    """Test get_user_score unique action counting logic with repeated actions."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    # Sequence where unique counting logic is exercised
    actions = ["a", "a", "b", "a", "c", "b"]
    activities = [
        {"timestamp": (base + timedelta(minutes=i)).isoformat(), "action": act}
        for i, act in enumerate(actions)
    ]
    score = activity_analyzer.get_user_score(activities)

    # According to implementation, unique_actions is count of first occurrences
    # of each action in order: 'a', 'b', 'c' -> 3
    total_actions = len(actions)
    unique_actions = 3
    first_dt = datetime.fromisoformat(activities[0]["timestamp"])
    last_dt = datetime.fromisoformat(activities[-1]["timestamp"])
    days_active = max((last_dt - first_dt).days, 1)
    actions_per_day = total_actions / days_active
    diversity_score = unique_actions / total_actions
    frequency_score = min(actions_per_day / 10.0, 1.0)
    volume_score = min(total_actions / 100.0, 1.0)
    expected = (diversity_score * 0.3 + frequency_score * 0.4 + volume_score * 0.3) * 100

    assert score == pytest.approx(round(expected, 2))


# -----------------------
# detect_anomalies tests
# -----------------------


def test_activityanalyzer_detect_anomalies_too_few_activities(activity_analyzer):
    """Test detect_anomalies returns empty when fewer than 5 activities."""
    activities = [
        {"timestamp": "2024-01-01T10:00:00Z", "action": "a"},
        {"timestamp": "2024-01-01T10:01:00Z", "action": "a"},
        {"timestamp": "2024-01-01T10:02:00Z", "action": "a"},
        {"timestamp": "2024-01-01T10:03:00Z", "action": "a"},
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert anomalies == []


def test_activityanalyzer_detect_anomalies_no_anomalies(activity_analyzer):
    """Test detect_anomalies returns empty when intervals are regular."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    # 6 actions of same type at regular 10-minute intervals
    activities = [
        {"timestamp": (base + timedelta(minutes=10 * i)).isoformat(), "action": "a"}
        for i in range(6)
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert anomalies == []


def test_activityanalyzer_detect_anomalies_with_anomaly(activity_analyzer):
    """Test detect_anomalies flags intervals with high z-score as anomalies."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    # Mostly 10-minute intervals, one very large interval to create anomaly
    timestamps = [
        base,
        base + timedelta(minutes=10),
        base + timedelta(minutes=20),
        base + timedelta(minutes=30),
        base + timedelta(hours=5),  # large gap
        base + timedelta(hours=5, minutes=10),
    ]
    activities = [
        {"timestamp": ts.isoformat(), "action": "a"} for ts in timestamps
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)

    # Depending on distribution, at least one anomaly should be detected
    assert len(anomalies) >= 1
    for anomaly in anomalies:
        assert anomaly["action"] == "a"
        assert "Unusual interval" in anomaly["reason"]
        assert isinstance(anomaly["z_score"], float) or isinstance(anomaly["z_score"], int)


def test_activityanalyzer_detect_anomalies_ignores_actions_with_few_timestamps(activity_analyzer):
    """Test detect_anomalies ignores actions with fewer than 3 timestamps."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = [
        {"timestamp": (base + timedelta(minutes=10 * i)).isoformat(), "action": "a"}
        for i in range(3)
    ] + [
        {"timestamp": (base + timedelta(minutes=5 * i)).isoformat(), "action": "b"}
        for i in range(2)
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)
    # Only 'a' has 3 timestamps, but intervals are regular so no anomalies
    assert anomalies == []


def test_activityanalyzer_detect_anomalies_invalid_timestamps(activity_analyzer):
    """Test detect_anomalies handles invalid timestamps gracefully."""
    activities = [
        {"timestamp": "invalid", "action": "a"},
        {"timestamp": "invalid", "action": "a"},
        {"timestamp": "invalid", "action": "a"},
        {"timestamp": "invalid", "action": "a"},
        {"timestamp": "invalid", "action": "a"},
    ]
    anomalies = activity_analyzer.detect_anomalies(activities)
    assert anomalies == []


# -----------------------
# Exception / robustness tests
# -----------------------


def test_activityanalyzer_analyze_patterns_handles_internal_exception(activity_analyzer, sample_activities):
    """Test analyze_patterns propagates exceptions from internal methods."""
    with patch.object(ActivityAnalyzer, "_detect_peak_hours", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            activity_analyzer.analyze_patterns(sample_activities)


def test_activityanalyzer_detect_anomalies_multiple_actions(activity_analyzer):
    """Test detect_anomalies processes multiple actions independently."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    activities = []
    # Action 'a' regular
    for i in range(5):
        activities.append({"timestamp": (base + timedelta(minutes=10 * i)).isoformat(), "action": "a"})
    # Action 'b' with one large gap to create anomaly
    b_times = [
        base,
        base + timedelta(minutes=5),
        base + timedelta(minutes=10),
        base + timedelta(hours=3),
        base + timedelta(hours=3, minutes=5),
    ]
    for ts in b_times:
        activities.append({"timestamp": ts.isoformat(), "action": "b"})

    anomalies = activity_analyzer.detect_anomalies(activities)
    # Expect anomalies only for 'b'
    assert all(a["action"] == "b" for a in anomalies) or anomalies == []  # depending on z-score threshold


def test_activityanalyzer_get_user_score_timestamp_order(activity_analyzer):
    """Test get_user_score uses first and last activity in list order, not sorted."""
    base = datetime(2024, 1, 10, 10, 0, 0)
    # Out-of-order timestamps; method uses first and last as given
    activities = [
        {"timestamp": (base + timedelta(days=5)).isoformat(), "action": "a"},  # first in list (later date)
        {"timestamp": (base).isoformat(), "action": "b"},
        {"timestamp": (base + timedelta(days=1)).isoformat(), "action": "c"},
    ]
    score = activity_analyzer.get_user_score(activities)

    total_actions = 3
    unique_actions = 3
    first_dt = datetime.fromisoformat(activities[0]["timestamp"])
    last_dt = datetime.fromisoformat(activities[-1]["timestamp"])
    days_active = max((last_dt - first_dt).days, 1)
    actions_per_day = total_actions / days_active
    diversity_score = unique_actions / total_actions
    frequency_score = min(actions_per_day / 10.0, 1.0)
    volume_score = min(total_actions / 100.0, 1.0)
    expected = (diversity_score * 0.3 + frequency_score * 0.4 + volume_score * 0.3) * 100

    assert score == pytest.approx(round(expected, 2))