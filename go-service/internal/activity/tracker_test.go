package activity

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestNewTracker_InitialState(t *testing.T) {
	tr := NewTracker()
	assert.NotNil(t, tr)
	assert.NotNil(t, tr.activities)
	assert.Equal(t, 0, tr.idCounter)
	assert.Equal(t, 0, len(tr.activities))
}

func TestTracker_LogActivity_Basic(t *testing.T) {
	tr := NewTracker()
	metadata := map[string]interface{}{"ip": "127.0.0.1"}

	log := tr.LogActivity("user1", "login", metadata)

	assert.NotNil(t, log)
	assert.Equal(t, "user1", log.UserID)
	assert.Equal(t, "login", log.Action)
	assert.Equal(t, metadata, log.Metadata)
	assert.NotEmpty(t, log.ID)
	assert.False(t, log.Timestamp.IsZero())

	// Ensure it was stored
	logs := tr.GetActivityByUser("user1")
	assert.Len(t, logs, 1)
	assert.Equal(t, log.ID, logs[0].ID)
}

func TestTracker_LogActivity_IDCounterIncrements(t *testing.T) {
	tr := NewTracker()

	log1 := tr.LogActivity("user1", "a1", nil)
	log2 := tr.LogActivity("user1", "a2", nil)

	assert.NotEqual(t, log1.ID, log2.ID)
	assert.Equal(t, 2, tr.idCounter)
}

func TestTracker_GetActivityByUser_EmptyForUnknownUser(t *testing.T) {
	tr := NewTracker()

	logs := tr.GetActivityByUser("unknown")
	assert.NotNil(t, logs)
	assert.Len(t, logs, 0)
}

func TestTracker_GetActivityByUser_ReturnsCopy(t *testing.T) {
	tr := NewTracker()
	tr.LogActivity("user1", "a1", nil)
	tr.LogActivity("user1", "a2", nil)

	logs := tr.GetActivityByUser("user1")
	assert.Len(t, logs, 2)

	// Mutate returned slice and ensure internal state is not affected
	logs[0].Action = "modified"

	internal := tr.GetActivityByUser("user1")
	assert.Equal(t, "a1", internal[0].Action)
}

func TestTracker_GetActivityStats_NoActivity(t *testing.T) {
	tr := NewTracker()

	stats := tr.GetActivityStats("unknown")
	assert.NotNil(t, stats)
	assert.Equal(t, 0, stats.TotalActions)
	assert.Equal(t, 0, stats.UniqueActions)
	assert.NotNil(t, stats.ActionCounts)
	assert.Equal(t, 0, len(stats.ActionCounts))
	assert.True(t, stats.FirstActivity.IsZero())
	assert.True(t, stats.LastActivity.IsZero())
	assert.Equal(t, "", stats.MostFrequent)
}

func TestTracker_GetActivityStats_SingleUserMultipleActions(t *testing.T) {
	tr := NewTracker()

	// Use fixed timestamps to make ordering deterministic
	base := time.Now().Add(-time.Hour)
	// Manually insert logs to control timestamps
	tr.activities["user1"] = []ActivityLog{
		{ID: "1", UserID: "user1", Action: "login", Timestamp: base.Add(10 * time.Minute)},
		{ID: "2", UserID: "user1", Action: "view", Timestamp: base.Add(20 * time.Minute)},
		{ID: "3", UserID: "user1", Action: "login", Timestamp: base.Add(30 * time.Minute)},
	}

	stats := tr.GetActivityStats("user1")
	assert.NotNil(t, stats)
	assert.Equal(t, 3, stats.TotalActions)
	assert.Equal(t, 2, stats.UniqueActions)
	assert.Equal(t, 2, stats.ActionCounts["login"])
	assert.Equal(t, 1, stats.ActionCounts["view"])
	assert.Equal(t, base.Add(10*time.Minute), stats.FirstActivity)
	assert.Equal(t, base.Add(30*time.Minute), stats.LastActivity)
	assert.Equal(t, "login", stats.MostFrequent)
}

func TestTracker_GetActivityStats_TimestampsOrderIndependence(t *testing.T) {
	tr := NewTracker()
	base := time.Now().Add(-time.Hour)

	// Out-of-order timestamps
	tr.activities["user1"] = []ActivityLog{
		{ID: "1", UserID: "user1", Action: "a", Timestamp: base.Add(30 * time.Minute)},
		{ID: "2", UserID: "user1", Action: "a", Timestamp: base.Add(10 * time.Minute)},
		{ID: "3", UserID: "user1", Action: "b", Timestamp: base.Add(20 * time.Minute)},
	}

	stats := tr.GetActivityStats("user1")
	assert.Equal(t, base.Add(10*time.Minute), stats.FirstActivity)
	assert.Equal(t, base.Add(30*time.Minute), stats.LastActivity)
}

func TestTracker_GetActivityByDateRange_NoUser(t *testing.T) {
	tr := NewTracker()
	start := time.Now().Add(-time.Hour)
	end := time.Now()

	logs := tr.GetActivityByDateRange("unknown", start, end)
	assert.NotNil(t, logs)
	assert.Len(t, logs, 0)
}

func TestTracker_GetActivityByDateRange_InclusiveBounds(t *testing.T) {
	tr := NewTracker()
	base := time.Now().Add(-time.Hour)

	log1 := ActivityLog{ID: "1", UserID: "user1", Action: "a1", Timestamp: base}
	log2 := ActivityLog{ID: "2", UserID: "user1", Action: "a2", Timestamp: base.Add(30 * time.Minute)}
	log3 := ActivityLog{ID: "3", UserID: "user1", Action: "a3", Timestamp: base.Add(60 * time.Minute)}

	tr.activities["user1"] = []ActivityLog{log1, log2, log3}

	// Range includes first and last exactly
	start := base
	end := base.Add(60 * time.Minute)

	logs := tr.GetActivityByDateRange("user1", start, end)
	assert.Len(t, logs, 3)

	// Range excludes first
	start2 := base.Add(1 * time.Nanosecond)
	logs2 := tr.GetActivityByDateRange("user1", start2, end)
	assert.Len(t, logs2, 2)

	// Range excludes last
	end2 := base.Add(60*time.Minute - 1*time.Nanosecond)
	logs3 := tr.GetActivityByDateRange("user1", start, end2)
	assert.Len(t, logs3, 2)
}

func TestTracker_GetActivityByDateRange_EmptyWhenOutside(t *testing.T) {
	tr := NewTracker()
	base := time.Now().Add(-time.Hour)

	tr.activities["user1"] = []ActivityLog{
		{ID: "1", UserID: "user1", Action: "a1", Timestamp: base},
	}

	start := base.Add(10 * time.Minute)
	end := base.Add(20 * time.Minute)

	logs := tr.GetActivityByDateRange("user1", start, end)
	assert.Len(t, logs, 0)
}

func TestTracker_GetAllUsers_Empty(t *testing.T) {
	tr := NewTracker()
	users := tr.GetAllUsers()
	assert.NotNil(t, users)
	assert.Len(t, users, 0)
}

func TestTracker_GetAllUsers_Sorted(t *testing.T) {
	tr := NewTracker()
	tr.LogActivity("userB", "a1", nil)
	tr.LogActivity("userA", "a2", nil)
	tr.LogActivity("userC", "a3", nil)

	users := tr.GetAllUsers()
	assert.Equal(t, []string{"userA", "userB", "userC"}, users)
}

func TestTracker_DeleteUserActivity_UserExists(t *testing.T) {
	tr := NewTracker()
	tr.LogActivity("user1", "a1", nil)
	tr.LogActivity("user2", "a2", nil)

	ok := tr.DeleteUserActivity("user1")
	assert.True(t, ok)

	// Ensure user1 data removed, user2 remains
	logs1 := tr.GetActivityByUser("user1")
	logs2 := tr.GetActivityByUser("user2")
	assert.Len(t, logs1, 0)
	assert.Len(t, logs2, 1)
}

func TestTracker_DeleteUserActivity_UserNotExists(t *testing.T) {
	tr := NewTracker()
	tr.LogActivity("user1", "a1", nil)

	ok := tr.DeleteUserActivity("unknown")
	assert.False(t, ok)

	// Ensure existing data untouched
	logs := tr.GetActivityByUser("user1")
	assert.Len(t, logs, 1)
}

func TestGenerateID_FormatAndUniqueness(t *testing.T) {
	id1 := generateID(1)
	id2 := generateID(2)

	assert.NotEmpty(t, id1)
	assert.NotEmpty(t, id2)
	assert.NotEqual(t, id1, id2)
	// Basic sanity: should contain a dash separating timestamp and counter rune
	assert.Contains(t, id1, "-")
}

func TestFindMostFrequentAction_Empty(t *testing.T) {
	result := findMostFrequentAction(map[string]int{})
	assert.Equal(t, "", result)
}

func TestFindMostFrequentAction_SingleAndMultiple(t *testing.T) {
	counts := map[string]int{
		"login":  3,
		"view":   5,
		"logout": 2,
	}

	result := findMostFrequentAction(counts)
	assert.Equal(t, "view", result)
}

func TestFindMostFrequentAction_TieReturnsOneOfMax(t *testing.T) {
	counts := map[string]int{
		"a": 2,
		"b": 2,
	}

	result := findMostFrequentAction(counts)
	// In tie, any of the max is acceptable; just ensure it's one of them
	assert.Contains(t, []string{"a", "b"}, result)
}
