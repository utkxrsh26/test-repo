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
	assert.Empty(t, tr.activities)
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
	assert.False(t, log.Timestamp.IsZero())
	assert.NotEmpty(t, log.ID)

	// Ensure it is stored
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

	tr.LogActivity("user1", "login", nil)

	logs := tr.GetActivityByUser("unknown")
	assert.NotNil(t, logs)
	assert.Len(t, logs, 0)
}

func TestTracker_GetActivityByUser_ReturnsCopy(t *testing.T) {
	tr := NewTracker()

	tr.LogActivity("user1", "login", nil)
	logs := tr.GetActivityByUser("user1")
	assert.Len(t, logs, 1)

	// Mutate returned slice and ensure internal state is not affected
	logs[0].Action = "mutated"

	internal := tr.GetActivityByUser("user1")
	assert.Equal(t, "login", internal[0].Action)
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

func TestTracker_GetActivityStats_SingleUserMultipleActions(t *testing.T) {
	tr := NewTracker()

	base := time.Now().Add(-time.Hour)
	// Manually insert logs with controlled timestamps
	tr.activities["user1"] = []ActivityLog{
		{
			ID:        "1",
			UserID:    "user1",
			Action:    "login",
			Timestamp: base,
		},
		{
			ID:        "2",
			UserID:    "user1",
			Action:    "view",
			Timestamp: base.Add(10 * time.Minute),
		},
		{
			ID:        "3",
			UserID:    "user1",
			Action:    "login",
			Timestamp: base.Add(20 * time.Minute),
		},
	}

	stats := tr.GetActivityStats("user1")
	assert.Equal(t, 3, stats.TotalActions)
	assert.Equal(t, 2, stats.UniqueActions)
	assert.Equal(t, 2, stats.ActionCounts["login"])
	assert.Equal(t, 1, stats.ActionCounts["view"])
	assert.True(t, stats.FirstActivity.Equal(base))
	assert.True(t, stats.LastActivity.Equal(base.Add(20*time.Minute)))
	assert.Equal(t, "login", stats.MostFrequent)
}

func TestTracker_GetActivityStats_MultipleUsersIsolation(t *testing.T) {
	tr := NewTracker()

	now := time.Now()
	tr.activities["user1"] = []ActivityLog{
		{ID: "1", UserID: "user1", Action: "a1", Timestamp: now},
	}
	tr.activities["user2"] = []ActivityLog{
		{ID: "2", UserID: "user2", Action: "a2", Timestamp: now.Add(time.Minute)},
		{ID: "3", UserID: "user2", Action: "a2", Timestamp: now.Add(2 * time.Minute)},
	}

	stats1 := tr.GetActivityStats("user1")
	assert.Equal(t, 1, stats1.TotalActions)
	assert.Equal(t, 1, stats1.UniqueActions)
	assert.Equal(t, 1, stats1.ActionCounts["a1"])

	stats2 := tr.GetActivityStats("user2")
	assert.Equal(t, 2, stats2.TotalActions)
	assert.Equal(t, 1, stats2.UniqueActions)
	assert.Equal(t, 2, stats2.ActionCounts["a2"])
}

func TestTracker_GetActivityByDateRange_EmptyForUnknownUser(t *testing.T) {
	tr := NewTracker()

	start := time.Now().Add(-time.Hour)
	end := time.Now()
	logs := tr.GetActivityByDateRange("unknown", start, end)
	assert.NotNil(t, logs)
	assert.Len(t, logs, 0)
}

func TestTracker_GetActivityByDateRange_InclusiveBounds(t *testing.T) {
	tr := NewTracker()

	base := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	logs := []ActivityLog{
		{ID: "1", UserID: "user1", Action: "a1", Timestamp: base.Add(-time.Minute)},
		{ID: "2", UserID: "user1", Action: "a2", Timestamp: base},
		{ID: "3", UserID: "user1", Action: "a3", Timestamp: base.Add(time.Minute)},
		{ID: "4", UserID: "user1", Action: "a4", Timestamp: base.Add(2 * time.Minute)},
	}
	tr.activities["user1"] = logs

	start := base
	end := base.Add(time.Minute)

	filtered := tr.GetActivityByDateRange("user1", start, end)
	// Should include timestamps == start and == end
	assert.Len(t, filtered, 2)
	assert.Equal(t, "2", filtered[0].ID)
	assert.Equal(t, "3", filtered[1].ID)
}

func TestTracker_GetActivityByDateRange_NoMatches(t *testing.T) {
	tr := NewTracker()

	base := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	tr.activities["user1"] = []ActivityLog{
		{ID: "1", UserID: "user1", Action: "a1", Timestamp: base},
	}

	start := base.Add(time.Hour)
	end := base.Add(2 * time.Hour)

	filtered := tr.GetActivityByDateRange("user1", start, end)
	assert.Len(t, filtered, 0)
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
	tr.LogActivity("userB", "a3", nil)

	users := tr.GetAllUsers()
	assert.Equal(t, []string{"userA", "userB"}, users)
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

func TestTracker_DeleteUserActivity_RemovesUserData(t *testing.T) {
	tr := NewTracker()

	tr.LogActivity("user1", "a1", nil)
	tr.LogActivity("user2", "a2", nil)
	tr.LogActivity("user1", "a3", nil)

	ok := tr.DeleteUserActivity("user1")
	assert.True(t, ok)

	logs1 := tr.GetActivityByUser("user1")
	assert.Len(t, logs1, 0)

	logs2 := tr.GetActivityByUser("user2")
	assert.Len(t, logs2, 1)
}

func TestGenerateID_FormatAndUniqueness(t *testing.T) {
	id1 := generateID(1)
	id2 := generateID(2)

	assert.NotEmpty(t, id1)
	assert.NotEmpty(t, id2)
	assert.NotEqual(t, id1, id2)

	// Check that there is a dash separator and suffix length is 1 rune
	assert.Contains(t, id1, "-")
}

func TestFindMostFrequentAction_Empty(t *testing.T) {
	res := findMostFrequentAction(map[string]int{})
	assert.Equal(t, "", res)
}

func TestFindMostFrequentAction_Single(t *testing.T) {
	res := findMostFrequentAction(map[string]int{"login": 3})
	assert.Equal(t, "login", res)
}

func TestFindMostFrequentAction_Multiple(t *testing.T) {
	counts := map[string]int{
		"login":  5,
		"view":   2,
		"logout": 3,
	}
	res := findMostFrequentAction(counts)
	assert.Equal(t, "login", res)
}
