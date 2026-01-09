package activity

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestNewTracker(t *testing.T) {
	tr := NewTracker()
	assert.NotNil(t, tr)
	assert.NotNil(t, tr.activities)
	assert.Equal(t, 0, tr.idCounter)
}

func TestTracker_LogActivity_Basic(t *testing.T) {
	tr := NewTracker()
	userID := "user1"
	action := "login"
	metadata := map[string]interface{}{"ip": "127.0.0.1"}

	log := tr.LogActivity(userID, action, metadata)

	assert.NotNil(t, log)
	assert.Equal(t, userID, log.UserID)
	assert.Equal(t, action, log.Action)
	assert.Equal(t, metadata, log.Metadata)
	assert.NotEmpty(t, log.ID)
	assert.WithinDuration(t, time.Now(), log.Timestamp, time.Second)

	// Ensure it was stored
	logs := tr.GetActivityByUser(userID)
	assert.Len(t, logs, 1)
	assert.Equal(t, *log, logs[0])
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
	userID := "user1"

	tr.LogActivity(userID, "a1", nil)
	original := tr.GetActivityByUser(userID)
	assert.Len(t, original, 1)

	// Mutate returned slice and ensure internal state is not affected
	original[0].Action = "mutated"

	again := tr.GetActivityByUser(userID)
	assert.Equal(t, "a1", again[0].Action)
}

func TestTracker_GetActivityStats_NoActivity(t *testing.T) {
	tr := NewTracker()

	stats := tr.GetActivityStats("user1")
	assert.NotNil(t, stats)
	assert.Equal(t, 0, stats.TotalActions)
	assert.Equal(t, 0, stats.UniqueActions)
	assert.NotNil(t, stats.ActionCounts)
	assert.Empty(t, stats.ActionCounts)
	assert.True(t, stats.FirstActivity.IsZero())
	assert.True(t, stats.LastActivity.IsZero())
	assert.Equal(t, "", stats.MostFrequent)
}

func TestTracker_GetActivityStats_WithActivities(t *testing.T) {
	tr := NewTracker()
	userID := "user1"

	// Use fixed timestamps to avoid flakiness
	base := time.Now().Add(-time.Hour)
	// Manually insert logs to control timestamps
	tr.activities[userID] = []ActivityLog{
		{
			ID:        "1",
			UserID:    userID,
			Action:    "login",
			Timestamp: base,
		},
		{
			ID:        "2",
			UserID:    userID,
			Action:    "view",
			Timestamp: base.Add(10 * time.Minute),
		},
		{
			ID:        "3",
			UserID:    userID,
			Action:    "login",
			Timestamp: base.Add(20 * time.Minute),
		},
	}

	stats := tr.GetActivityStats(userID)
	assert.NotNil(t, stats)
	assert.Equal(t, 3, stats.TotalActions)
	assert.Equal(t, 2, stats.UniqueActions)
	assert.Equal(t, 2, stats.ActionCounts["login"])
	assert.Equal(t, 1, stats.ActionCounts["view"])
	assert.Equal(t, base, stats.FirstActivity)
	assert.Equal(t, base.Add(20*time.Minute), stats.LastActivity)
	assert.Equal(t, "login", stats.MostFrequent)
}

func TestTracker_GetActivityStats_SingleActionType(t *testing.T) {
	tr := NewTracker()
	userID := "user1"

	now := time.Now()
	tr.activities[userID] = []ActivityLog{
		{ID: "1", UserID: userID, Action: "only", Timestamp: now},
	}

	stats := tr.GetActivityStats(userID)
	assert.Equal(t, 1, stats.TotalActions)
	assert.Equal(t, 1, stats.UniqueActions)
	assert.Equal(t, "only", stats.MostFrequent)
}

func TestTracker_GetActivityByDateRange_NoUser(t *testing.T) {
	tr := NewTracker()
	start := time.Now().Add(-time.Hour)
	end := time.Now()

	logs := tr.GetActivityByDateRange("unknown", start, end)
	assert.NotNil(t, logs)
	assert.Len(t, logs, 0)
}

func TestTracker_GetActivityByDateRange_Filtering(t *testing.T) {
	tr := NewTracker()
	userID := "user1"

	base := time.Now().Add(-2 * time.Hour)
	logs := []ActivityLog{
		{ID: "1", UserID: userID, Action: "a1", Timestamp: base},
		{ID: "2", UserID: userID, Action: "a2", Timestamp: base.Add(30 * time.Minute)},
		{ID: "3", UserID: userID, Action: "a3", Timestamp: base.Add(90 * time.Minute)},
	}
	tr.activities[userID] = logs

	start := base.Add(30 * time.Minute)
	end := base.Add(90 * time.Minute)

	filtered := tr.GetActivityByDateRange(userID, start, end)
	// Should include boundaries: logs[1] and logs[2]
	assert.Len(t, filtered, 2)
	assert.Equal(t, "2", filtered[0].ID)
	assert.Equal(t, "3", filtered[1].ID)
}

func TestTracker_GetActivityByDateRange_ExactBoundaryMatch(t *testing.T) {
	tr := NewTracker()
	userID := "user1"

	base := time.Now()
	log := ActivityLog{ID: "1", UserID: userID, Action: "a", Timestamp: base}
	tr.activities[userID] = []ActivityLog{log}

	filtered := tr.GetActivityByDateRange(userID, base, base)
	assert.Len(t, filtered, 1)
	assert.Equal(t, log.ID, filtered[0].ID)
}

func TestTracker_GetAllUsers_Empty(t *testing.T) {
	tr := NewTracker()

	users := tr.GetAllUsers()
	assert.NotNil(t, users)
	assert.Len(t, users, 0)
}

func TestTracker_GetAllUsers_SortedAndUnique(t *testing.T) {
	tr := NewTracker()

	tr.LogActivity("userB", "a1", nil)
	tr.LogActivity("userA", "a2", nil)
	tr.LogActivity("userC", "a3", nil)
	tr.LogActivity("userA", "a4", nil)

	users := tr.GetAllUsers()
	assert.Equal(t, []string{"userA", "userB", "userC"}, users)
}

func TestTracker_DeleteUserActivity_UserNotExists(t *testing.T) {
	tr := NewTracker()

	ok := tr.DeleteUserActivity("unknown")
	assert.False(t, ok)
}

func TestTracker_DeleteUserActivity_RemovesUserData(t *testing.T) {
	tr := NewTracker()

	tr.LogActivity("user1", "a1", nil)
	tr.LogActivity("user2", "a2", nil)
	tr.LogActivity("user1", "a3", nil)

	ok := tr.DeleteUserActivity("user1")
	assert.True(t, ok)

	// user1 should be gone
	logs1 := tr.GetActivityByUser("user1")
	assert.Len(t, logs1, 0)

	// user2 should remain
	logs2 := tr.GetActivityByUser("user2")
	assert.Len(t, logs2, 1)
	assert.Equal(t, "user2", logs2[0].UserID)
}

func TestGenerateID_FormatAndUniqueness(t *testing.T) {
	id1 := generateID(1)
	time.Sleep(10 * time.Millisecond)
	id2 := generateID(2)

	assert.NotEmpty(t, id1)
	assert.NotEmpty(t, id2)
	assert.NotEqual(t, id1, id2)
	// Basic format check: contains a dash
	assert.Contains(t, id1, "-")
	assert.Contains(t, id2, "-")
}

func TestFindMostFrequentAction_Empty(t *testing.T) {
	result := findMostFrequentAction(map[string]int{})
	assert.Equal(t, "", result)
}

func TestFindMostFrequentAction_Single(t *testing.T) {
	result := findMostFrequentAction(map[string]int{"a": 1})
	assert.Equal(t, "a", result)
}

func TestFindMostFrequentAction_Multiple(t *testing.T) {
	counts := map[string]int{
		"login":  5,
		"view":   3,
		"logout": 2,
	}
	result := findMostFrequentAction(counts)
	assert.Equal(t, "login", result)
}

func TestFindMostFrequentAction_TieReturnsOneOfMax(t *testing.T) {
	counts := map[string]int{
		"a": 2,
		"b": 2,
	}
	result := findMostFrequentAction(counts)
	assert.Contains(t, []string{"a", "b"}, result)
}
