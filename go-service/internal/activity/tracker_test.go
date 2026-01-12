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

func TestTracker_GetActivityByUser_EmptyAndNonExisting(t *testing.T) {
	tr := NewTracker()

	// No activities at all
	logs := tr.GetActivityByUser("unknown")
	assert.NotNil(t, logs)
	assert.Len(t, logs, 0)

	// Add for another user
	tr.LogActivity("user1", "login", nil)
	logs = tr.GetActivityByUser("user2")
	assert.NotNil(t, logs)
	assert.Len(t, logs, 0)
}

func TestTracker_GetActivityByUser_ReturnsCopy(t *testing.T) {
	tr := NewTracker()
	userID := "user1"

	tr.LogActivity(userID, "a1", nil)
	original := tr.GetActivityByUser(userID)
	assert.Len(t, original, 1)

	// Mutate returned slice and ensure internal state not affected
	original[0].Action = "mutated"

	again := tr.GetActivityByUser(userID)
	assert.Len(t, again, 1)
	assert.Equal(t, "a1", again[0].Action)
}

func TestTracker_GetActivityStats_NoActivity(t *testing.T) {
	tr := NewTracker()

	stats := tr.GetActivityStats("user1")
	assert.NotNil(t, stats)
	assert.Equal(t, 0, stats.TotalActions)
	assert.Equal(t, 0, stats.UniqueActions)
	assert.NotNil(t, stats.ActionCounts)
	assert.Equal(t, 0, len(stats.ActionCounts))
	// Source code leaves FirstActivity and LastActivity zero when no logs exist
	assert.True(t, stats.FirstActivity.IsZero())
	assert.True(t, stats.LastActivity.IsZero())
	assert.Equal(t, "", stats.MostFrequent)
}

func TestTracker_GetActivityStats_SingleUserMultipleActions(t *testing.T) {
	tr := NewTracker()
	userID := "user1"

	// Use fixed timestamps to make ordering deterministic
	base := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	logs := []ActivityLog{
		{UserID: userID, Action: "login", Timestamp: base.Add(2 * time.Minute)},
		{UserID: userID, Action: "click", Timestamp: base.Add(1 * time.Minute)},
		{UserID: userID, Action: "login", Timestamp: base.Add(3 * time.Minute)},
	}

	tr.mu.Lock()
	tr.activities[userID] = append(tr.activities[userID], logs...)
	tr.mu.Unlock()

	stats := tr.GetActivityStats(userID)
	assert.NotNil(t, stats)
	assert.Equal(t, 3, stats.TotalActions)
	assert.Equal(t, 2, stats.UniqueActions)
	assert.Equal(t, 2, stats.ActionCounts["login"])
	assert.Equal(t, 1, stats.ActionCounts["click"])
	assert.Equal(t, base.Add(1*time.Minute), stats.FirstActivity)
	assert.Equal(t, base.Add(3*time.Minute), stats.LastActivity)
	assert.Equal(t, "login", stats.MostFrequent)
}

func TestTracker_GetActivityStats_TieMostFrequent(t *testing.T) {
	tr := NewTracker()
	userID := "user1"

	base := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	logs := []ActivityLog{
		{UserID: userID, Action: "a", Timestamp: base},
		{UserID: userID, Action: "b", Timestamp: base.Add(1 * time.Minute)},
	}

	tr.mu.Lock()
	tr.activities[userID] = append(tr.activities[userID], logs...)
	tr.mu.Unlock()

	stats := tr.GetActivityStats(userID)
	assert.NotNil(t, stats)
	assert.Equal(t, 2, stats.TotalActions)
	assert.Equal(t, 2, stats.UniqueActions)
	assert.Equal(t, 1, stats.ActionCounts["a"])
	assert.Equal(t, 1, stats.ActionCounts["b"])
	assert.True(t, stats.MostFrequent == "a" || stats.MostFrequent == "b")
}

func TestTracker_GetActivityByDateRange_NoUser(t *testing.T) {
	tr := NewTracker()
	start := time.Now().Add(-time.Hour)
	end := time.Now().Add(time.Hour)

	logs := tr.GetActivityByDateRange("unknown", start, end)
	assert.NotNil(t, logs)
	assert.Len(t, logs, 0)
}

func TestTracker_GetActivityByDateRange_InclusiveBounds(t *testing.T) {
	tr := NewTracker()
	userID := "user1"

	base := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	logs := []ActivityLog{
		{UserID: userID, Action: "before", Timestamp: base.Add(-1 * time.Minute)},
		{UserID: userID, Action: "start", Timestamp: base},
		{UserID: userID, Action: "middle", Timestamp: base.Add(30 * time.Minute)},
		{UserID: userID, Action: "end", Timestamp: base.Add(1 * time.Hour)},
		{UserID: userID, Action: "after", Timestamp: base.Add(2 * time.Hour)},
	}

	tr.mu.Lock()
	tr.activities[userID] = append(tr.activities[userID], logs...)
	tr.mu.Unlock()

	start := base
	end := base.Add(1 * time.Hour)

	filtered := tr.GetActivityByDateRange(userID, start, end)
	assert.Len(t, filtered, 3)
	actions := []string{filtered[0].Action, filtered[1].Action, filtered[2].Action}
	assert.Contains(t, actions, "start")
	assert.Contains(t, actions, "middle")
	assert.Contains(t, actions, "end")
}

func TestTracker_GetActivityByDateRange_EmptyRange(t *testing.T) {
	tr := NewTracker()
	userID := "user1"

	base := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	tr.mu.Lock()
	tr.activities[userID] = append(tr.activities[userID], ActivityLog{
		UserID:    userID,
		Action:    "only",
		Timestamp: base,
	})
	tr.mu.Unlock()

	// start after end -> no results
	start := base.Add(1 * time.Hour)
	end := base

	filtered := tr.GetActivityByDateRange(userID, start, end)
	assert.Len(t, filtered, 0)
}

func TestTracker_GetAllUsers_Empty(t *testing.T) {
	tr := NewTracker()
	users := tr.GetAllUsers()
	assert.NotNil(t, users)
	assert.Len(t, users, 0)
}

func TestTracker_GetAllUsers_SortedUnique(t *testing.T) {
	tr := NewTracker()

	tr.LogActivity("userB", "a", nil)
	tr.LogActivity("userA", "b", nil)
	tr.LogActivity("userC", "c", nil)
	tr.LogActivity("userA", "d", nil)

	users := tr.GetAllUsers()
	assert.Equal(t, []string{"userA", "userB", "userC"}, users)
}

func TestTracker_DeleteUserActivity_NonExisting(t *testing.T) {
	tr := NewTracker()

	ok := tr.DeleteUserActivity("unknown")
	assert.False(t, ok)
}

func TestTracker_DeleteUserActivity_Existing(t *testing.T) {
	tr := NewTracker()

	tr.LogActivity("user1", "a", nil)
	tr.LogActivity("user2", "b", nil)

	ok := tr.DeleteUserActivity("user1")
	assert.True(t, ok)

	logs1 := tr.GetActivityByUser("user1")
	assert.Len(t, logs1, 0)

	logs2 := tr.GetActivityByUser("user2")
	assert.Len(t, logs2, 1)
}

func TestGenerateID_FormatAndUniqueness(t *testing.T) {
	id1 := generateID(1)

	// generateID uses time format "20060102150405" (14 chars) + "-" + single-rune counter (1 char) = 16 total
	// However, the counter is converted via string(rune(counter)), so for counter=1 this is the rune with codepoint 1,
	// which is a non-printable character. We only assert overall length and that two different counters yield different IDs.

	assert.Len(t, id1, 16)

	id2 := generateID(2)
	assert.Len(t, id2, 16)
	assert.NotEqual(t, id1, id2)
}

func TestFindMostFrequentAction_Empty(t *testing.T) {
	result := findMostFrequentAction(map[string]int{})
	assert.Equal(t, "", result)
}

func TestFindMostFrequentAction_Single(t *testing.T) {
	result := findMostFrequentAction(map[string]int{"a": 3})
	assert.Equal(t, "a", result)
}

func TestFindMostFrequentAction_Multiple(t *testing.T) {
	counts := map[string]int{
		"a": 1,
		"b": 5,
		"c": 3,
	}
	result := findMostFrequentAction(counts)
	assert.Equal(t, "b", result)
}

func TestFindMostFrequentAction_Tie(t *testing.T) {
	counts := map[string]int{
		"a": 2,
		"b": 2,
	}
	result := findMostFrequentAction(counts)
	assert.True(t, result == "a" || result == "b")
}
