package activity

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestNewTracker(t *testing.T) {
	tracker := NewTracker()
	assert.NotNil(t, tracker)
	assert.NotNil(t, tracker.activities)
	assert.Equal(t, 0, tracker.idCounter)
}

func TestTracker_LogActivity_Basic(t *testing.T) {
	tracker := NewTracker()
	userID := "user1"
	action := "login"
	metadata := map[string]interface{}{"ip": "127.0.0.1"}

	log := tracker.LogActivity(userID, action, metadata)

	assert.NotNil(t, log)
	assert.Equal(t, userID, log.UserID)
	assert.Equal(t, action, log.Action)
	assert.Equal(t, metadata, log.Metadata)
	assert.NotEmpty(t, log.ID)
	assert.WithinDuration(t, time.Now(), log.Timestamp, time.Second)

	// Ensure it is stored
	logs := tracker.GetActivityByUser(userID)
	assert.Len(t, logs, 1)
	assert.Equal(t, log.ID, logs[0].ID)
}

func TestTracker_LogActivity_IDCounterIncrements(t *testing.T) {
	tracker := NewTracker()
	log1 := tracker.LogActivity("user1", "a1", nil)
	log2 := tracker.LogActivity("user1", "a2", nil)

	assert.NotEqual(t, log1.ID, log2.ID)
	assert.Equal(t, 2, tracker.idCounter)
}

func TestTracker_GetActivityByUser_Empty(t *testing.T) {
	tracker := NewTracker()

	logs := tracker.GetActivityByUser("nonexistent")

	assert.NotNil(t, logs)
	assert.Len(t, logs, 0)
}

func TestTracker_GetActivityByUser_CopyIsolation(t *testing.T) {
	tracker := NewTracker()
	userID := "user1"

	tracker.LogActivity(userID, "a1", nil)
	original := tracker.GetActivityByUser(userID)
	assert.Len(t, original, 1)

	// Modify returned slice and ensure internal state is not affected
	original[0].Action = "modified"

	internal := tracker.GetActivityByUser(userID)
	assert.Equal(t, "a1", internal[0].Action)
}

func TestTracker_GetActivityStats_NoActivity(t *testing.T) {
	tracker := NewTracker()

	stats := tracker.GetActivityStats("user1")

	assert.NotNil(t, stats)
	assert.Equal(t, 0, stats.TotalActions)
	assert.Equal(t, 0, stats.UniqueActions)
	assert.NotNil(t, stats.ActionCounts)
	assert.Equal(t, 0, len(stats.ActionCounts))
	assert.True(t, stats.FirstActivity.IsZero())
	assert.True(t, stats.LastActivity.IsZero())
	assert.Equal(t, "", stats.MostFrequent)
}

func TestTracker_GetActivityStats_WithActivities(t *testing.T) {
	tracker := NewTracker()
	userID := "user1"

	// Create deterministic timestamps
	base := time.Now().Add(-time.Hour)
	// Manually insert logs to control timestamps
	tracker.activities[userID] = []ActivityLog{
		{
			ID:        "1",
			UserID:    userID,
			Action:    "login",
			Timestamp: base.Add(10 * time.Minute),
		},
		{
			ID:        "2",
			UserID:    userID,
			Action:    "view",
			Timestamp: base.Add(20 * time.Minute),
		},
		{
			ID:        "3",
			UserID:    userID,
			Action:    "login",
			Timestamp: base.Add(30 * time.Minute),
		},
	}

	stats := tracker.GetActivityStats(userID)

	assert.NotNil(t, stats)
	assert.Equal(t, 3, stats.TotalActions)
	assert.Equal(t, 2, stats.UniqueActions)
	assert.Equal(t, 2, stats.ActionCounts["login"])
	assert.Equal(t, 1, stats.ActionCounts["view"])
	assert.Equal(t, base.Add(10*time.Minute), stats.FirstActivity)
	assert.Equal(t, base.Add(30*time.Minute), stats.LastActivity)
	assert.Equal(t, "login", stats.MostFrequent)
}

func TestTracker_GetActivityByDateRange_NoUser(t *testing.T) {
	tracker := NewTracker()
	start := time.Now().Add(-time.Hour)
	end := time.Now()

	logs := tracker.GetActivityByDateRange("missing", start, end)
	assert.NotNil(t, logs)
	assert.Len(t, logs, 0)
}

func TestTracker_GetActivityByDateRange_Filtering(t *testing.T) {
	tracker := NewTracker()
	userID := "user1"
	base := time.Now().Add(-2 * time.Hour)

	logs := []ActivityLog{
		{
			ID:        "1",
			UserID:    userID,
			Action:    "a1",
			Timestamp: base.Add(10 * time.Minute),
		},
		{
			ID:        "2",
			UserID:    userID,
			Action:    "a2",
			Timestamp: base.Add(30 * time.Minute),
		},
		{
			ID:        "3",
			UserID:    userID,
			Action:    "a3",
			Timestamp: base.Add(50 * time.Minute),
		},
	}
	tracker.activities[userID] = logs

	start := base.Add(20 * time.Minute)
	end := base.Add(50 * time.Minute)

	filtered := tracker.GetActivityByDateRange(userID, start, end)

	// Should include logs[1] (30m) and logs[2] (50m, inclusive)
	assert.Len(t, filtered, 2)
	assert.Equal(t, "2", filtered[0].ID)
	assert.Equal(t, "3", filtered[1].ID)
}

func TestTracker_GetActivityByDateRange_BoundaryInclusive(t *testing.T) {
	tracker := NewTracker()
	userID := "user1"
	base := time.Now().Add(-time.Hour)

	log := ActivityLog{
		ID:        "1",
		UserID:    userID,
		Action:    "a1",
		Timestamp: base,
	}
	tracker.activities[userID] = []ActivityLog{log}

	start := base
	end := base

	filtered := tracker.GetActivityByDateRange(userID, start, end)
	assert.Len(t, filtered, 1)
	assert.Equal(t, "1", filtered[0].ID)
}

func TestTracker_GetAllUsers_Empty(t *testing.T) {
	tracker := NewTracker()

	users := tracker.GetAllUsers()
	assert.NotNil(t, users)
	assert.Len(t, users, 0)
}

func TestTracker_GetAllUsers_Sorted(t *testing.T) {
	tracker := NewTracker()
	tracker.activities["userB"] = []ActivityLog{}
	tracker.activities["userA"] = []ActivityLog{}
	tracker.activities["userC"] = []ActivityLog{}

	users := tracker.GetAllUsers()
	assert.Equal(t, []string{"userA", "userB", "userC"}, users)
}

func TestTracker_DeleteUserActivity_Nonexistent(t *testing.T) {
	tracker := NewTracker()

	ok := tracker.DeleteUserActivity("missing")
	assert.False(t, ok)
}

func TestTracker_DeleteUserActivity_Existing(t *testing.T) {
	tracker := NewTracker()
	userID := "user1"
	tracker.activities[userID] = []ActivityLog{
		{ID: "1", UserID: userID, Action: "a1", Timestamp: time.Now()},
	}

	ok := tracker.DeleteUserActivity(userID)
	assert.True(t, ok)

	logs := tracker.GetActivityByUser(userID)
	assert.Len(t, logs, 0)
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
		"a": 1,
		"b": 3,
		"c": 2,
	}
	result := findMostFrequentAction(counts)
	assert.Equal(t, "b", result)
}

func TestGenerateID_FormatAndUniqueness(t *testing.T) {
	id1 := generateID(1)
	id2 := generateID(2)

	assert.NotEmpty(t, id1)
	assert.NotEmpty(t, id2)
	assert.NotEqual(t, id1, id2)

	// Basic format check: should contain a dash
	assert.Contains(t, id1, "-")
}
