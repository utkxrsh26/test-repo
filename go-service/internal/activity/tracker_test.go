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
	meta := map[string]interface{}{"ip": "127.0.0.1"}

	log := tr.LogActivity("user1", "login", meta)

	assert.NotNil(t, log)
	assert.Equal(t, "user1", log.UserID)
	assert.Equal(t, "login", log.Action)
	assert.Equal(t, meta, log.Metadata)
	assert.NotEmpty(t, log.ID)
	assert.False(t, log.Timestamp.IsZero())

	// Ensure it is stored
	logs := tr.GetActivityByUser("user1")
	assert.Len(t, logs, 1)
	assert.Equal(t, log.ID, logs[0].ID)
}

func TestTracker_LogActivity_IDCounterIncrements(t *testing.T) {
	tr := NewTracker()

	log1 := tr.LogActivity("user1", "a1", nil)
	log2 := tr.LogActivity("user1", "a2", nil)
	log3 := tr.LogActivity("user2", "a3", nil)

	assert.NotEqual(t, log1.ID, log2.ID)
	assert.NotEqual(t, log2.ID, log3.ID)
	assert.Equal(t, 3, tr.idCounter)
}

func TestTracker_GetActivityByUser_EmptyAndIsolation(t *testing.T) {
	tr := NewTracker()

	// No activities yet
	logs := tr.GetActivityByUser("unknown")
	assert.NotNil(t, logs)
	assert.Len(t, logs, 0)

	// Add activities for multiple users
	tr.LogActivity("user1", "a1", nil)
	tr.LogActivity("user1", "a2", nil)
	tr.LogActivity("user2", "b1", nil)

	logsUser1 := tr.GetActivityByUser("user1")
	logsUser2 := tr.GetActivityByUser("user2")

	assert.Len(t, logsUser1, 2)
	assert.Len(t, logsUser2, 1)

	// Ensure returned slice is a copy (modifying it does not affect tracker)
	logsUser1[0].Action = "modified"
	logsUser1Again := tr.GetActivityByUser("user1")
	assert.NotEqual(t, "modified", logsUser1Again[0].Action)
}

func TestTracker_GetActivityStats_NoUserOrNoLogs(t *testing.T) {
	tr := NewTracker()

	// No such user
	stats := tr.GetActivityStats("nouser")
	assert.NotNil(t, stats)
	assert.Equal(t, 0, stats.TotalActions)
	assert.Equal(t, 0, stats.UniqueActions)
	assert.NotNil(t, stats.ActionCounts)
	assert.Equal(t, 0, len(stats.ActionCounts))
	assert.True(t, stats.FirstActivity.IsZero())
	assert.True(t, stats.LastActivity.IsZero())
	assert.Equal(t, "", stats.MostFrequent)

	// User exists but no logs (should behave same as no user)
	tr.activities["emptyuser"] = []ActivityLog{}
	stats2 := tr.GetActivityStats("emptyuser")
	assert.NotNil(t, stats2)
	assert.Equal(t, 0, stats2.TotalActions)
	assert.Equal(t, 0, stats2.UniqueActions)
	assert.NotNil(t, stats2.ActionCounts)
	assert.Equal(t, 0, len(stats2.ActionCounts))
	assert.True(t, stats2.FirstActivity.IsZero())
	assert.True(t, stats2.LastActivity.IsZero())
	assert.Equal(t, "", stats2.MostFrequent)
}

func TestTracker_GetActivityStats_WithLogs(t *testing.T) {
	tr := NewTracker()

	base := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	logs := []ActivityLog{
		{
			ID:        "1",
			UserID:    "user1",
			Action:    "login",
			Timestamp: base.Add(2 * time.Minute),
		},
		{
			ID:        "2",
			UserID:    "user1",
			Action:    "click",
			Timestamp: base.Add(5 * time.Minute),
		},
		{
			ID:        "3",
			UserID:    "user1",
			Action:    "login",
			Timestamp: base.Add(1 * time.Minute),
		},
	}
	tr.activities["user1"] = logs

	stats := tr.GetActivityStats("user1")
	assert.NotNil(t, stats)
	assert.Equal(t, 3, stats.TotalActions)
	assert.Equal(t, 2, stats.UniqueActions)
	assert.Equal(t, 2, stats.ActionCounts["login"])
	assert.Equal(t, 1, stats.ActionCounts["click"])
	assert.Equal(t, base.Add(1*time.Minute), stats.FirstActivity)
	assert.Equal(t, base.Add(5*time.Minute), stats.LastActivity)
	assert.Equal(t, "login", stats.MostFrequent)
}

func TestTracker_GetActivityByDateRange_NoUserOrNoMatch(t *testing.T) {
	tr := NewTracker()

	start := time.Now().Add(-time.Hour)
	end := time.Now().Add(time.Hour)

	// No such user
	logs := tr.GetActivityByDateRange("nouser", start, end)
	assert.NotNil(t, logs)
	assert.Len(t, logs, 0)

	// User with logs but none in range
	base := time.Now()
	tr.activities["user1"] = []ActivityLog{
		{UserID: "user1", Action: "a1", Timestamp: base.Add(-2 * time.Hour)},
		{UserID: "user1", Action: "a2", Timestamp: base.Add(2 * time.Hour)},
	}

	logs2 := tr.GetActivityByDateRange("user1", base.Add(-30*time.Minute), base.Add(30*time.Minute))
	assert.NotNil(t, logs2)
	assert.Len(t, logs2, 0)
}

func TestTracker_GetActivityByDateRange_InclusiveBounds(t *testing.T) {
	tr := NewTracker()

	base := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	logs := []ActivityLog{
		{UserID: "user1", Action: "before", Timestamp: base.Add(-time.Minute)},
		{UserID: "user1", Action: "start", Timestamp: base},
		{UserID: "user1", Action: "middle", Timestamp: base.Add(30 * time.Minute)},
		{UserID: "user1", Action: "end", Timestamp: base.Add(time.Hour)},
		{UserID: "user1", Action: "after", Timestamp: base.Add(time.Hour + time.Minute)},
	}
	tr.activities["user1"] = logs

	start := base
	end := base.Add(time.Hour)

	filtered := tr.GetActivityByDateRange("user1", start, end)
	assert.Len(t, filtered, 3)
	var actions []string
	for _, l := range filtered {
		actions = append(actions, l.Action)
	}
	assert.Contains(t, actions, "start")
	assert.Contains(t, actions, "middle")
	assert.Contains(t, actions, "end")
}

func TestTracker_GetAllUsers_EmptyAndSorted(t *testing.T) {
	tr := NewTracker()

	// No users
	users := tr.GetAllUsers()
	assert.NotNil(t, users)
	assert.Len(t, users, 0)

	// Add users in unsorted order
	tr.activities["charlie"] = []ActivityLog{{UserID: "charlie"}}
	tr.activities["alice"] = []ActivityLog{{UserID: "alice"}}
	tr.activities["bob"] = []ActivityLog{{UserID: "bob"}}

	users = tr.GetAllUsers()
	assert.Equal(t, []string{"alice", "bob", "charlie"}, users)
}

func TestTracker_DeleteUserActivity_Behavior(t *testing.T) {
	tr := NewTracker()

	tr.activities["user1"] = []ActivityLog{
		{UserID: "user1", Action: "a1"},
	}
	tr.activities["user2"] = []ActivityLog{
		{UserID: "user2", Action: "b1"},
	}

	// Delete non-existent user
	ok := tr.DeleteUserActivity("nouser")
	assert.False(t, ok)
	assert.Contains(t, tr.activities, "user1")
	assert.Contains(t, tr.activities, "user2")

	// Delete existing user
	ok = tr.DeleteUserActivity("user1")
	assert.True(t, ok)
	_, exists := tr.activities["user1"]
	assert.False(t, exists)
	_, exists = tr.activities["user2"]
	assert.True(t, exists)
}

func TestGenerateID_FormatAndUniqueness(t *testing.T) {
	id1 := generateID(1)
	id2 := generateID(2)

	assert.NotEmpty(t, id1)
	assert.NotEmpty(t, id2)
	assert.NotEqual(t, id1, id2)

	// Check that there is a dash and something after it
	assert.Contains(t, id1, "-")
}

func TestFindMostFrequentAction_Empty(t *testing.T) {
	result := findMostFrequentAction(map[string]int{})
	assert.Equal(t, "", result)
}

func TestFindMostFrequentAction_SingleAndMultiple(t *testing.T) {
	counts := map[string]int{
		"login":  3,
		"click":  1,
		"logout": 2,
	}
	result := findMostFrequentAction(counts)
	assert.Equal(t, "login", result)

	// Tie case: ensure deterministic in sense of "one of the max"; exact one is not guaranteed
	countsTie := map[string]int{
		"a": 2,
		"b": 2,
	}
	resultTie := findMostFrequentAction(countsTie)
	assert.True(t, resultTie == "a" || resultTie == "b")
}
