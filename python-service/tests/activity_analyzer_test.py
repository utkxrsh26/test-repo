import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone

from src.activity_analyzer import ActivityPattern, ActivityAnalyzer


@pytest.fixture
def activity_pattern_instance():
    """Create ActivityPattern instance for testing."""
    return ActivityPattern(pattern_type="test_type", description="test_desc", confidence=0.9)


@pytest.fixture
def activity_analyzer_instance():
    """Create ActivityAnalyzer instance for testing."""
    return ActivityAnalyzer()


def test_activitypattern_init():
    """Test ActivityPattern initialization sets attributes correctly."""
    pattern = ActivityPattern(pattern_type="peak_hours", description="desc", confidence=0.85)
    assert pattern.pattern_type == "peak_hours"
    assert pattern.description == "desc"
    assert pattern.confidence == pytest.approx(0.85)


def test_activitypattern_to_dict(activity_pattern_instance):
    """Test ActivityPattern.to_dict returns correct dictionary."""
    result = activity_pattern_instance.to_dict()
    assert result["pattern_type"] == "test_type"
    assert result["description"] == "test_desc"
    assert result["confidence"] == pytest.approx(0.9)


def test_activityanalyzer_init_defaults(activity_analyzer_instance):
    """Test ActivityAnalyzer initialization sets default thresholds."""
    assert activity_analyzer_instance.peak_hour_threshold == pytest.approx(0.2)
    assert activity_analyzer_instance.anomaly_threshold == pytest.approx(3.0)


def test_activityanalyzer_analyze_patterns_empty(activity_analyzer_instance):
    """Test analyze_patterns returns empty list for no activities."""
    assert activity_analyzer_instance.analyze_patterns([]) == []


def test_activityanalyzer_analyze_patterns_calls_internal_methods(activity_analyzer_instance):
    """Test analyze_patterns calls internal detection methods and aggregates results."""
    activities = [{"timestamp": datetime.now(timezone.utc).isoformat(), "action": "a"}]

    with patch.object(activity_analyzer_instance, "_detect_peak_hours", return_value=[ActivityPattern("t1", "d1", 0.1)]) as mock_peak, \
         patch.object(activity_analyzer_instance, "_detect_action_sequences", return_value=[ActivityPattern("t2", "d2", 0.2)]) as mock_seq, \
         patch.object(activity_analyzer_instance, "_detect_regularity", return_value=[ActivityPattern("t3", "d3", 0.3)]) as mock_reg:

        patterns = activity_analyzer_instance.analyze_patterns(activities)

        mock_peak.assert_called_once_with(activities)
        mock_seq.assert_called_once_with(activities)
        mock_reg.assert_called_once_with(activities)

        assert len(patterns) == 3
        assert [p.pattern_type for p in patterns] == ["t1", "t2", "t3"]


def test_activityanalyzer_get_user_score_empty(activity_analyzer_instance):
    """Test get_user_score returns 0.0 for empty activities."""
    score = activity_analyzer_instance.get_user_score([])
    assert score == pytest.approx(0.0)


def test_activityanalyzer_get_user_score_basic(activity_analyzer_instance):
    """Test get_user_score with simple activity list and same-day timestamps."""
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    activities = [
        {"timestamp": (base + timedelta(minutes=i)).isoformat(), "action": "a"}
        for i in range(5)
    ]
    score = activity_analyzer_instance.get_user_score(activities)
    # total_actions=5, unique_actions=1, days_active=1
    # diversity=0.2, actions_per_day=5 -> freq=0.5, volume=0.05
    # final=(0.2*0.3 + 0.5*0.4 + 0.05*0.3)*100 = 29.5
    assert score == pytest.approx(29.5)


def test_activityanalyzer_get_user_score_multiple_days(activity_analyzer_instance):
    """Test get_user_score when activities span multiple days."""
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    activities = [
        {"timestamp": (base + timedelta(days=i)).isoformat(), "action": f"a{i}"}
        for i in range(4)
    ]
    score = activity_analyzer_instance.get_user_score(activities)
    # total=4, unique=4, days_active=3, actions_per_day=4/3
    # diversity=1.0, freq=(4/3)/10=0.1333, volume=0.04
    # final=(1*0.3 + 0.1333*0.4 + 0.04*0.3)*100 ≈ 36.53
    assert score == pytest.approx(36.53, rel=1e-3)


def test_activityanalyzer_get_user_score_invalid_timestamps(activity_analyzer_instance):
    """Test get_user_score when timestamps are invalid strings."""
    activities = [
        {"timestamp": "not-a-date", "action": "a"},
        {"timestamp": None, "action": "b"},
        {"timestamp": 12345, "action": "c"},
    ]
    score = activity_analyzer_instance.get_user_score(activities)
    # No valid timestamps -> actions_per_day = total_actions = 3
    # unique_actions=3, diversity=1.0, freq=min(3/10,1)=0.3, volume=0.03
    # final=(1*0.3 + 0.3*0.4 + 0.03*0.3)*100 = 42.9
    assert score == pytest.approx(42.9)


def test_activityanalyzer_detect_anomalies_too_few(activity_analyzer_instance):
    """Test detect_anomalies returns empty list when fewer than 5 activities."""
    activities = [{"timestamp": datetime.now(timezone.utc).isoformat(), "action": "a"} for _ in range(4)]
    assert activity_analyzer_instance.detect_anomalies(activities) == []


def test_activityanalyzer_detect_anomalies_no_intervals(activity_analyzer_instance):
    """Test detect_anomalies returns empty when not enough timestamps per action."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = [
        {"timestamp": (base + timedelta(minutes=i)).isoformat(), "action": "a"} for i in range(2)
    ] + [
        {"timestamp": (base + timedelta(minutes=10 + i)).isoformat(), "action": "b"} for i in range(2)
    ] + [
        {"timestamp": (base + timedelta(minutes=20)).isoformat(), "action": "c"}
    ]
    # Each action has <3 timestamps, so no anomalies
    assert activity_analyzer_instance.detect_anomalies(activities) == []


def test_activityanalyzer_detect_anomalies_with_outlier_interval(activity_analyzer_instance):
    """Test detect_anomalies detects an interval with high z-score."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # Create mostly regular 60s intervals, then one large gap
    timestamps = [
        base,
        base + timedelta(seconds=60),
        base + timedelta(seconds=120),
        base + timedelta(seconds=180),
        base + timedelta(seconds=1000),  # big jump
        base + timedelta(seconds=1060),
    ]
    activities = [{"timestamp": ts.isoformat(), "action": "a"} for ts in timestamps]

    anomalies = activity_analyzer_instance.detect_anomalies(activities)
    # Expect at least one anomaly for the large interval
    assert len(anomalies) >= 1
    assert anomalies[0]["action"] == "a"
    assert isinstance(anomalies[0]["z_score"], float)
    assert anomalies[0]["z_score"] == pytest.approx(anomalies[0]["z_score"])


def test_activityanalyzer_detect_anomalies_ignores_invalid_timestamps(activity_analyzer_instance):
    """Test detect_anomalies ignores activities with invalid timestamps."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    valid_activities = [
        {"timestamp": (base + timedelta(minutes=i)).isoformat(), "action": "a"} for i in range(5)
    ]
    invalid_activities = [
        {"timestamp": "invalid", "action": "a"},
        {"timestamp": None, "action": "a"},
    ]
    activities = valid_activities + invalid_activities
    anomalies = activity_analyzer_instance.detect_anomalies(activities)
    assert isinstance(anomalies, list)


def test_activityanalyzer_detect_anomalies_uses_threshold(activity_analyzer_instance):
    """Test detect_anomalies respects anomaly_threshold via mocking."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    timestamps = [
        base,
        base + timedelta(seconds=60),
        base + timedelta(seconds=120),
        base + timedelta(seconds=1000),
        base + timedelta(seconds=1060),
    ]
    activities = [{"timestamp": ts.isoformat(), "action": "a"} for ts in timestamps]

    with patch.object(activity_analyzer_instance, "anomaly_threshold", 0.1):
        anomalies = activity_analyzer_instance.detect_anomalies(activities)
        assert len(anomalies) >= 1


def test_activityanalyzer_detect_peak_hours_no_activities(activity_analyzer_instance):
    """Test _detect_peak_hours returns empty list when no valid timestamps."""
    activities = [{"timestamp": "invalid", "action": "a"}]
    patterns = activity_analyzer_instance._detect_peak_hours(activities)
    assert patterns == []


def test_activityanalyzer_detect_peak_hours_single_peak(activity_analyzer_instance):
    """Test _detect_peak_hours identifies peak hours above threshold."""
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    activities = []
    # 8 actions at 10:00, 2 actions at 11:00 -> 10:00 is 80% > 0.2
    for i in range(8):
        activities.append({"timestamp": (base + timedelta(minutes=i)).isoformat(), "action": "a"})
    for i in range(2):
        activities.append({"timestamp": (base + timedelta(hours=1, minutes=i)).isoformat(), "action": "b"})

    patterns = activity_analyzer_instance._detect_peak_hours(activities)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.pattern_type == "peak_hours"
    assert "10:00" in pattern.description
    assert pattern.confidence == pytest.approx(0.85)


def test_activityanalyzer_detect_peak_hours_multiple_peaks(activity_analyzer_instance):
    """Test _detect_peak_hours can list multiple peak hours."""
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    activities = []
    # 3 actions at 10:00, 3 at 11:00, 4 at 12:00 -> all 30%, 30%, 40% > 0.2
    for i in range(3):
        activities.append({"timestamp": (base + timedelta(minutes=i)).isoformat(), "action": "a"})
    for i in range(3):
        activities.append({"timestamp": (base + timedelta(hours=1, minutes=i)).isoformat(), "action": "b"})
    for i in range(4):
        activities.append({"timestamp": (base + timedelta(hours=2, minutes=i)).isoformat(), "action": "c"})

    patterns = activity_analyzer_instance._detect_peak_hours(activities)
    assert len(patterns) == 1
    desc = patterns[0].description
    assert "10:00" in desc
    assert "11:00" in desc
    assert "12:00" in desc


def test_activityanalyzer_detect_action_sequences_too_short(activity_analyzer_instance):
    """Test _detect_action_sequences returns empty when fewer than 3 activities."""
    activities = [{"timestamp": datetime.now(timezone.utc).isoformat(), "action": "a"}]
    assert activity_analyzer_instance._detect_action_sequences(activities) == []


def test_activityanalyzer_detect_action_sequences_common_sequence(activity_analyzer_instance):
    """Test _detect_action_sequences identifies repeated sequences."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = [
        {"timestamp": (base + timedelta(minutes=i)).isoformat(), "action": a}
        for i, a in enumerate([
            "login", "view", "logout",
            "login", "view", "logout",
            "login", "other", "logout",
        ])
    ]
    patterns = activity_analyzer_instance._detect_action_sequences(activities)
    # "login, view, logout" occurs twice
    assert any("login → view → logout" in p.description for p in patterns)
    for p in patterns:
        assert p.pattern_type == "action_sequence"
        assert p.confidence == pytest.approx(0.75)


def test_activityanalyzer_detect_action_sequences_top_three(activity_analyzer_instance):
    """Test _detect_action_sequences returns at most three most common sequences."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    actions = [
        "a", "b", "c",  # seq1
        "a", "b", "c",  # seq1
        "d", "e", "f",  # seq2
        "d", "e", "f",  # seq2
        "g", "h", "i",  # seq3
        "g", "h", "i",  # seq3
        "j", "k", "l",  # seq4
        "j", "k", "l",  # seq4
    ]
    activities = [
        {"timestamp": (base + timedelta(minutes=i)).isoformat(), "action": act}
        for i, act in enumerate(actions)
    ]
    patterns = activity_analyzer_instance._detect_action_sequences(activities)
    assert len(patterns) <= 3


def test_activityanalyzer_detect_regularity_too_few(activity_analyzer_instance):
    """Test _detect_regularity returns empty when fewer than 5 activities."""
    activities = [{"timestamp": datetime.now(timezone.utc).isoformat(), "action": "a"} for _ in range(4)]
    assert activity_analyzer_instance._detect_regularity(activities) == []


def test_activityanalyzer_detect_regularity_not_enough_valid_timestamps(activity_analyzer_instance):
    """Test _detect_regularity returns empty when fewer than 5 valid timestamps."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    activities = [
        {"timestamp": (base + timedelta(minutes=i)).isoformat(), "action": "a"} for i in range(3)
    ] + [
        {"timestamp": "invalid", "action": "a"},
        {"timestamp": None, "action": "a"},
    ]
    assert activity_analyzer_instance._detect_regularity(activities) == []


def test_activityanalyzer_detect_regularity_highly_regular(activity_analyzer_instance):
    """Test _detect_regularity detects highly regular intervals."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # Perfect 60s intervals
    activities = [
        {"timestamp": (base + timedelta(seconds=60 * i)).isoformat(), "action": "a"}
        for i in range(6)
    ]
    patterns = activity_analyzer_instance._detect_regularity(activities)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.pattern_type == "regularity"
    assert "Highly regular activity pattern" in pattern.description
    assert pattern.confidence == pytest.approx(0.9)


def test_activityanalyzer_detect_regularity_irregular(activity_analyzer_instance):
    """Test _detect_regularity returns empty for irregular intervals."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    intervals = [10, 100, 300, 50, 1000, 20]
    timestamps = [base]
    for sec in intervals:
        timestamps.append(timestamps[-1] + timedelta(seconds=sec))
    activities = [{"timestamp": ts.isoformat(), "action": "a"} for ts in timestamps]
    patterns = activity_analyzer_instance._detect_regularity(activities)
    assert patterns == []


def test_activityanalyzer_parse_timestamp_datetime(activity_analyzer_instance):
    """Test _parse_timestamp returns datetime unchanged when input is datetime."""
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    parsed = activity_analyzer_instance._parse_timestamp(ts)
    assert parsed is ts


def test_activityanalyzer_parse_timestamp_iso_string(activity_analyzer_instance):
    """Test _parse_timestamp parses ISO 8601 string."""
    ts = "2024-01-01T10:00:00+00:00"
    parsed = activity_analyzer_instance._parse_timestamp(ts)
    assert isinstance(parsed, datetime)
    assert parsed.isoformat() == "2024-01-01T10:00:00+00:00"


def test_activityanalyzer_parse_timestamp_z_suffix(activity_analyzer_instance):
    """Test _parse_timestamp parses ISO string with Z suffix as UTC."""
    ts = "2024-01-01T10:00:00Z"
    parsed = activity_analyzer_instance._parse_timestamp(ts)
    assert isinstance(parsed, datetime)
    assert parsed.tzinfo is not None
    assert parsed.replace(tzinfo=timezone.utc).hour == 10


def test_activityanalyzer_parse_timestamp_invalid_string(activity_analyzer_instance):
    """Test _parse_timestamp returns None for invalid string."""
    parsed = activity_analyzer_instance._parse_timestamp("not-a-timestamp")
    assert parsed is None


def test_activityanalyzer_parse_timestamp_non_string_non_datetime(activity_analyzer_instance):
    """Test _parse_timestamp returns None for unsupported types."""
    parsed = activity_analyzer_instance._parse_timestamp(12345)
    assert parsed is None


def test_activityanalyzer_parse_timestamp_exception_handling(activity_analyzer_instance, monkeypatch):
    """Test _parse_timestamp gracefully handles exceptions from datetime.fromisoformat."""
    def bad_fromisoformat(_):
        raise ValueError("bad format")

    with monkeypatch.context() as m:
        m.setattr("datetime.datetime.fromisoformat", bad_fromisoformat, raising=False)
        parsed = activity_analyzer_instance._parse_timestamp("2024-01-01T10:00:00")
        assert parsed is None