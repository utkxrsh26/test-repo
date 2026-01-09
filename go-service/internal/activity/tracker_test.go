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

	// Ensure it is stored
	stored := tr.GetActivityByUser(userID)
	assert.Len(t, stored, 1)
	assert.Equal(t, *log, stored[0])
}

func TestTracker_LogActivity_IDCounterIncrements(t *testing.T) {
	tr := NewTracker()

	log1 := tr.LogActivity("user1", "a1", nil)
	log2 := tr.LogActivity("user1", "a2", nil)

	assert.NotEqual(t, log1.ID, log2.ID)
	assert.Equal(t, 2, tr.idCounter)
}

func TestTracker_GetActivityByUser_EmptyAndIsolation(t *testing.T) {
	tr := NewTracker()

	// No activities yet
	logs := tr.GetActivityByUser("unknown")
	assert.NotNil(t, logs)
	assert.Len(t, logs, 0)

	// Add activities for multiple users
	tr.LogActivity("user1", "a1", nil)
	tr.LogActivity("user2", "a2", nil)
	tr.LogActivity("user1", "a3", nil)

	u1 := tr.GetActivityByUser("user1")
	u2 := tr.GetActivityByUser("user2")

	assert.Len(t, u1, 2)
	assert.Len(t, u2, 1)

	// Ensure returned slice is a copy (modifying it does not affect tracker)
	u1[0].Action = "modified"
	u1Again := tr.GetActivityByUser("user1")
	assert.NotEqual(t, "modified", u1Again[0].Action)
}

func TestTracker_GetActivityStats_NoUserOrNoLogs(t *testing.T) {
	tr := NewTracker()

	// No such user
	stats := tr.GetActivityStats("nouser")
	assert.NotNil(t, stats)
	assert.Equal(t, 0, stats.TotalActions)
	assert.Equal(t, 0, stats.UniqueActions)
	assert.NotNil(t, stats.ActionCounts)
	assert.Empty(t, stats.ActionCounts)
	assert.True(t, stats.FirstActivity.IsZero())
	assert.True(t, stats.LastActivity.IsZero())
	assert.Equal(t, "", stats.MostFrequent)

	// User exists but no logs (not possible with current implementation,
	// but we can simulate by direct map manipulation)
	tr.activities["emptyUser"] = []ActivityLog{}
	stats2 := tr.GetActivityStats("emptyUser")
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
	userID := "user1"

	base := time.Now().Add(-time.Hour)
	// Manually control timestamps to avoid time.Now() variability
	tr.mu.Lock()
	tr.idCounter++
	log1 := ActivityLog{
		ID:        generateID(tr.idCounter),
		UserID:    userID,
		Action:    "login",
		Timestamp: base,
	}
	tr.idCounter++
	log2 := ActivityLog{
		ID:        generateID(tr.idCounter),
		UserID:    userID,
		Action:    "click",
		Timestamp: base.Add(10 * time.Minute),
	}
	tr.idCounter++
	log3 := ActivityLog{
		ID:        generateID(tr.idCounter),
		UserID:    userID,
		Action:    "login",
		Timestamp: base.Add(20 * time.Minute),
	}
	tr.activities[userID] = []ActivityLog{log1, log2, log3}
	tr.mu.Unlock()

	stats := tr.GetActivityStats(userID)
	assert.NotNil(t, stats)
	assert.Equal(t, 3, stats.TotalActions)
	assert.Equal(t, 2, stats.UniqueActions)
	assert.Equal(t, 2, stats.ActionCounts["login"])
	assert.Equal(t, 1, stats.ActionCounts["click"])
	assert.Equal(t, base, stats.FirstActivity)
	assert.Equal(t, base.Add(20*time.Minute), stats.LastActivity)
	assert.Equal(t, "login", stats.MostFrequent)
}

func TestTracker_GetActivityByDateRange_NoUserOrNoMatch(t *testing.T) {
	tr := NewTracker()
	start := time.Now().Add(-time.Hour)
	end := time.Now().Add(time.Hour)

	// No such user
	res := tr.GetActivityByDateRange("nouser", start, end)
	assert.NotNil(t, res)
	assert.Len(t, res, 0)

	// User with logs but none in range
	userID := "user1"
	tr.mu.Lock()
	tr.activities[userID] = []ActivityLog{
		{UserID: userID, Action: "a1", Timestamp: start.Add(-2 * time.Hour)},
		{UserID: userID, Action: "a2", Timestamp: end.Add(2 * time.Hour)},
	}
	tr.mu.Unlock()

	res2 := tr.GetActivityByDateRange(userID, start, end)
	assert.NotNil(t, res2)
	assert.Len(t, res2, 0)
}

func TestTracker_GetActivityByDateRange_InclusiveBounds(t *testing.T) {
	tr := NewTracker()
	userID := "user1"
	base := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	start := base
	end := base.Add(2 * time.Hour)

	tr.mu.Lock()
	tr.activities[userID] = []ActivityLog{
		{UserID: userID, Action: "before", Timestamp: base.Add(-time.Minute)},
		{UserID: userID, Action: "start", Timestamp: start},
		{UserID: userID, Action: "middle", Timestamp: base.Add(time.Hour)},
		{UserID: userID, Action: "end", Timestamp: end},
		{UserID: userID, Action: "after", Timestamp: end.Add(time.Minute)},
	}
	tr.mu.Unlock()

	res := tr.GetActivityByDateRange(userID, start, end)
	assert.Len(t, res, 3)
	var actions []string
	for _, l := range res {
		actions = append(actions, l.Action)
	}
	assert.Contains(t, actions, "start")
	assert.Contains(t, actions, "middle")
	assert.Contains(t, actions, "end")
}

func TestTracker_GetAllUsers_EmptyAndSorted(t *testing.T) {
	tr := NewTracker()

	// Empty
	users := tr.GetAllUsers()
	assert.NotNil(t, users)
	assert.Len(t, users, 0)

	// With users
	tr.LogActivity("userB", "a1", nil)
	tr.LogActivity("userA", "a2", nil)
	tr.LogActivity("userC", "a3", nil)
	tr.LogActivity("userA", "a4", nil)

	users = tr.GetAllUsers()
	assert.Equal(t, []string{"userA", "userB", "userC"}, users)
}

func TestTracker_DeleteUserActivity(t *testing.T) {
	tr := NewTracker()

	tr.LogActivity("user1", "a1", nil)
	tr.LogActivity("user2", "a2", nil)
	tr.LogActivity("user1", "a3", nil)

	// Delete non-existing user
	ok := tr.DeleteUserActivity("nouser")
	assert.False(t, ok)

	// Delete existing user
	ok = tr.DeleteUserActivity("user1")
	assert.True(t, ok)

	// Ensure activities removed
	u1 := tr.GetActivityByUser("user1")
	assert.Len(t, u1, 0)

	// Ensure other users unaffected
	u2 := tr.GetActivityByUser("user2")
	assert.Len(t, u2, 1)
	assert.Equal(t, "user2", u2[0].UserID)
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

func TestFindMostFrequentAction(t *testing.T) {
	tests := []struct {
		name         string
		actionCounts map[string]int
		expected     string
	}{
		{
			name:         "empty map",
			actionCounts: map[string]int{},
			expected:     "",
		},
		{
			name: "single action",
			actionCounts: map[string]int{
				"login": 3,
			},
			expected: "login",
		},
		{
			name: "multiple actions distinct counts",
			actionCounts: map[string]int{
				"login":  5,
				"click":  2,
				"logout": 1,
			},
			expected: "login",
		},
		{
			name: "tie chooses first max encountered (implementation-defined but stable per map iteration)",
			actionCounts: map[string]int{
				"a": 3,
				"b": 3,
			},
			// We can't reliably assert which one due to map iteration order,
			// but we can assert it is one of the keys.
			expected: "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := findMostFrequentAction(tt.actionCounts)
			if tt.expected != "" {
				assert.Equal(t, tt.expected, got)
			} else {
				if len(tt.actionCounts) == 0 {
					assert.Equal(t, "", got)
				} else {
					_, exists := tt.actionCounts[got]
					assert.True(t, exists)
				}
			}
		})
	}
}
