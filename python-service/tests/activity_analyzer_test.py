from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import math


@dataclass
class ActivityPattern:
    pattern_type: str
    description: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_type": self.pattern_type,
            "description": self.description,
            "confidence": self.confidence,
        }


class ActivityAnalyzer:
    def __init__(self, peak_hour_threshold: float = 0.2, anomaly_threshold: float = 3.0):
        self.peak_hour_threshold = peak_hour_threshold
        self.anomaly_threshold = anomaly_threshold

    # ---------------- Public API ----------------

    def analyze_patterns(self, activities: List[Dict[str, Any]]) -> List[ActivityPattern]:
        if not activities:
            return []

        patterns: List[ActivityPattern] = []
        patterns.extend(self._detect_peak_hours(activities))
        patterns.extend(self._detect_action_sequences(activities))
        patterns.extend(self._detect_regularity(activities))
        return patterns

    def get_user_score(self, activities: List[Dict[str, Any]]) -> float:
        if not activities:
            return 0.0

        total_actions = len(activities)

        # Diversity: count unique actions in order of first appearance
        seen = set()
        unique_actions = 0
        for act in activities:
            action = act.get("action")
            if action not in seen:
                seen.add(action)
                unique_actions += 1
        diversity_score = unique_actions / total_actions if total_actions else 0.0

        # Frequency: based on actions per active day
        first_ts = self._parse_timestamp(activities[0].get("timestamp"))
        last_ts = self._parse_timestamp(activities[-1].get("timestamp"))

        if first_ts is None or last_ts is None:
            # Fallback when timestamps cannot be parsed
            actions_per_day = float(total_actions)
        else:
            days_active = max((last_ts - first_ts).days, 1)
            actions_per_day = total_actions / days_active

        frequency_score = min(actions_per_day / 10.0, 1.0)
        volume_score = min(total_actions / 100.0, 1.0)

        score = (diversity_score * 0.3 + frequency_score * 0.4 + volume_score * 0.3) * 100
        return round(score, 2)

    def detect_anomalies(self, activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(activities) < 5:
            return []

        # Group timestamps by action
        action_timestamps: Dict[str, List[datetime]] = {}
        for act in activities:
            ts = self._parse_timestamp(act.get("timestamp"))
            if ts is None:
                continue
            action = act.get("action")
            action_timestamps.setdefault(action, []).append(ts)

        anomalies: List[Dict[str, Any]] = []

        for action, ts_list in action_timestamps.items():
            if len(ts_list) < 2:
                continue
            ts_list.sort()
            intervals = [
                (ts_list[i + 1] - ts_list[i]).total_seconds()
                for i in range(len(ts_list) - 1)
            ]
            if not intervals:
                continue

            mean = sum(intervals) / len(intervals)
            variance = sum((x - mean) ** 2 for x in intervals) / len(intervals)
            std_dev = math.sqrt(variance)

            if std_dev == 0:
                # No variation -> no anomalies
                continue

            for i, interval in enumerate(intervals):
                z = (interval - mean) / std_dev
                if abs(z) >= self.anomaly_threshold:
                    anomalies.append(
                        {
                            "action": action,
                            "timestamp": ts_list[i + 1].isoformat(),
                            "z_score": float(z),
                            "reason": "Anomalous interval between consecutive actions",
                        }
                    )

        return anomalies

    # ---------------- Internal helpers ----------------

    def _detect_peak_hours(self, activities: List[Dict[str, Any]]) -> List[ActivityPattern]:
        # Count activities per hour (HH:00)
        hour_counts: Dict[str, int] = {}
        total = 0
        for act in activities:
            ts = self._parse_timestamp(act.get("timestamp"))
            if ts is None:
                continue
            hour_str = ts.strftime("%H:00")
            hour_counts[hour_str] = hour_counts.get(hour_str, 0) + 1
            total += 1

        if total == 0:
            return []

        peak_hours: List[Tuple[str, float]] = []
        for hour, count in hour_counts.items():
            ratio = count / total
            if ratio >= self.peak_hour_threshold:
                peak_hours.append((hour, ratio))

        if not peak_hours:
            return []

        # Sort by ratio descending
        peak_hours.sort(key=lambda x: x[1], reverse=True)
        hours_str = ", ".join(h for h, _ in peak_hours)
        avg_ratio = sum(r for _, r in peak_hours) / len(peak_hours)

        description = f"High activity during hours: {hours_str}"
        confidence = round(0.5 + avg_ratio * 0.5, 2)
        return [ActivityPattern("peak_hours", description, confidence)]

    def _detect_action_sequences(self, activities: List[Dict[str, Any]]) -> List[ActivityPattern]:
        if len(activities) < 3:
            return []

        # Build sequences of length 3
        seq_counts: Dict[Tuple[str, str, str], int] = {}
        for i in range(len(activities) - 2):
            a1 = activities[i].get("action")
            a2 = activities[i + 1].get("action")
            a3 = activities[i + 2].get("action")
            seq = (a1, a2, a3)
            seq_counts[seq] = seq_counts.get(seq, 0) + 1

        # Keep sequences that occur at least twice
        common = [(seq, cnt) for seq, cnt in seq_counts.items() if cnt >= 2]
        if not common:
            return []

        # Sort by count descending
        common.sort(key=lambda x: x[1], reverse=True)
        best_seq, count = common[0]
        seq_str = " -> ".join(best_seq)
        description = f"Common sequence: {seq_str} (occurred {count} times)"
        # Confidence based on frequency, capped at 0.95, baseline 0.5
        confidence = round(min(0.5 + (count - 1) * 0.25, 0.95), 2)
        return [ActivityPattern("action_sequence", description, confidence)]

    def _detect_regularity(self, activities: List[Dict[str, Any]]) -> List[ActivityPattern]:
        if len(activities) < 5:
            return []

        # Extract and sort valid timestamps
        timestamps: List[datetime] = []
        for act in activities:
            ts = self._parse_timestamp(act.get("timestamp"))
            if ts is not None:
                timestamps.append(ts)

        if len(timestamps) < 5:
            return []

        timestamps.sort()
        intervals = [
            (timestamps[i + 1] - timestamps[i]).total_seconds()
            for i in range(len(timestamps) - 1)
        ]
        if not intervals:
            return []

        mean = sum(intervals) / len(intervals)
        if mean == 0:
            return []

        variance = sum((x - mean) ** 2 for x in intervals) / len(intervals)
        std_dev = math.sqrt(variance)
        cv = std_dev / mean  # coefficient of variation

        # Consider highly regular if CV <= 0.1
        if cv <= 0.1:
            description = f"Highly regular activity pattern (CV: {cv:.2f})"
            confidence = 0.9
            return [ActivityPattern("regularity", description, confidence)]

        return []

    def _parse_timestamp(self, ts: Any) -> Optional[datetime]:
        if isinstance(ts, datetime):
            return ts

        if isinstance(ts, str):
            try:
                if ts.endswith("Z"):
                    # Treat Z as UTC
                    # Remove Z and parse, then set tzinfo to UTC
                    base = datetime.fromisoformat(ts[:-1])
                    if base.tzinfo is None:
                        base = base.replace(tzinfo=timezone.utc)
                    return base
                return datetime.fromisoformat(ts)
            except Exception:
                return None

        # Unsupported type
        return None