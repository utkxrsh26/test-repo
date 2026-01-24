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

func TestTracker_GetActivityByUser_NoActivities(t *testing.T) {
	tr := NewTracker()

	logs := tr.GetActivityByUser("unknown")
	assert.NotNil(t, logs)
	assert.Len(t, logs, 0)
}

func TestTracker_GetActivityByUser_ReturnsCopy(t *testing.T) {
	tr := NewTracker()
	_ = tr.LogActivity("user1", "a1", nil)

	logs := tr.GetActivityByUser("user1")
	assert.Len(t, logs, 1)

	// Mutate returned slice and ensure internal state is not affected
	logs[0].Action = "modified"

	internal := tr.GetActivityByUser("user1")
	assert.Equal(t, "a1", internal[0].Action)
}

func TestTracker_GetActivityStats_NoUserOrNoLogs(t *testing.T) {
	tr := NewTracker()

	stats := tr.GetActivityStats("unknown")
	assert.NotNil(t, stats)
	assert.Equal(t, 0, stats.TotalActions)
	assert.Equal(t, 0, stats.UniqueActions)
	assert.NotNil(t, stats.ActionCounts)
	assert.Empty(t, stats.ActionCounts)
	assert.True(t, stats.FirstActivity.IsZero())
	assert.True(t, stats.LastActivity.IsZero())
	assert.Equal(t, "", stats.MostFrequent)

	// User exists but with no logs (should behave the same)
	tr.activities["user1"] = []ActivityLog{}
	stats2 := tr.GetActivityStats("user1")
	assert.NotNil(t, stats2)
	assert.Equal(t, 0, stats2.TotalActions)
	assert.Equal(t, 0, stats2.UniqueActions)
	assert.NotNil(t, stats2.ActionCounts)
	assert.Empty(t, stats2.ActionCounts)
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
			Timestamp: base.Add(2 * time.Hour),
		},
		{
			ID:        "2",
			UserID:    "user1",
			Action:    "view",
			Timestamp: base.Add(1 * time.Hour),
		},
		{
			ID:        "3",
			UserID:    "user1",
			Action:    "login",
			Timestamp: base.Add(3 * time.Hour),
		},
	}
	tr.activities["user1"] = logs

	stats := tr.GetActivityStats("user1")
	assert.NotNil(t, stats)
	assert.Equal(t, 3, stats.TotalActions)
	assert.Equal(t, 2, stats.UniqueActions)
	assert.Equal(t, 2, stats.ActionCounts["login"])
	assert.Equal(t, 1, stats.ActionCounts["view"])
	assert.Equal(t, base.Add(1*time.Hour), stats.FirstActivity)
	assert.Equal(t, base.Add(3*time.Hour), stats.LastActivity)
	assert.Equal(t, "login", stats.MostFrequent)
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
	base := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)

	logs := []ActivityLog{
		{
			ID:        "1",
			UserID:    "user1",
			Action:    "before",
			Timestamp: base.Add(-time.Minute),
		},
		{
			ID:        "2",
			UserID:    "user1",
			Action:    "start",
			Timestamp: base,
		},
		{
			ID:        "3",
			UserID:    "user1",
			Action:    "middle",
			Timestamp: base.Add(30 * time.Minute),
		},
		{
			ID:        "4",
			UserID:    "user1",
			Action:    "end",
			Timestamp: base.Add(time.Hour),
		},
		{
			ID:        "5",
			UserID:    "user1",
			Action:    "after",
			Timestamp: base.Add(time.Hour + time.Minute),
		},
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
	assert.ElementsMatch(t, []string{"start", "middle", "end"}, actions)
}

func TestTracker_GetAllUsers_Empty(t *testing.T) {
	tr := NewTracker()
	users := tr.GetAllUsers()
	assert.NotNil(t, users)
	assert.Len(t, users, 0)
}

func TestTracker_GetAllUsers_SortedUnique(t *testing.T) {
	tr := NewTracker()
	tr.activities["b"] = []ActivityLog{{UserID: "b"}}
	tr.activities["a"] = []ActivityLog{{UserID: "a"}}
	tr.activities["c"] = []ActivityLog{{UserID: "c"}}

	users := tr.GetAllUsers()
	assert.Equal(t, []string{"a", "b", "c"}, users)
}

func TestTracker_DeleteUserActivity_UserNotExist(t *testing.T) {
	tr := NewTracker()
	tr.activities["user1"] = []ActivityLog{{UserID: "user1"}}

	ok := tr.DeleteUserActivity("unknown")
	assert.False(t, ok)
	assert.Contains(t, tr.activities, "user1")
}

func TestTracker_DeleteUserActivity_UserExists(t *testing.T) {
	tr := NewTracker()
	tr.activities["user1"] = []ActivityLog{{UserID: "user1"}}
	tr.activities["user2"] = []ActivityLog{{UserID: "user2"}}

	ok := tr.DeleteUserActivity("user1")
	assert.True(t, ok)
	_, exists := tr.activities["user1"]
	assert.False(t, exists)
	_, exists2 := tr.activities["user2"]
	assert.True(t, exists2)
}

func TestGenerateID_FormatAndUniqueness(t *testing.T) {
	id1 := generateID(1)
	id2 := generateID(2)

	assert.NotEmpty(t, id1)
	assert.NotEmpty(t, id2)
	assert.NotEqual(t, id1, id2)

	// Ensure it contains a dash separator
	assert.Contains(t, id1, "-")
}

func TestFindMostFrequentAction_Empty(t *testing.T) {
	result := findMostFrequentAction(map[string]int{})
	assert.Equal(t, "", result)
}

func TestFindMostFrequentAction_Single(t *testing.T) {
	result := findMostFrequentAction(map[string]int{"login": 3})
	assert.Equal(t, "login", result)
}

func TestFindMostFrequentAction_Multiple(t *testing.T) {
	counts := map[string]int{
		"login":  5,
		"view":   2,
		"logout": 3,
	}
	result := findMostFrequentAction(counts)
	assert.Equal(t, "login", result)
}

func TestFindMostFrequentAction_TieReturnsOneOfMax(t *testing.T) {
	counts := map[string]int{
		"a": 3,
		"b": 3,
		"c": 1,
	}
	result := findMostFrequentAction(counts)
	assert.Contains(t, []string{"a", "b"}, result)
}
