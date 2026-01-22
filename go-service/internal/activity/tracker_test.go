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
	assert.Empty(t, tr.activities)
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
	log3 := tr.LogActivity("user2", "a3", nil)

	assert.NotEqual(t, log1.ID, log2.ID)
	assert.NotEqual(t, log2.ID, log3.ID)
	assert.Equal(t, 3, tr.idCounter)
}

func TestTracker_GetActivityByUser_EmptyAndNonExisting(t *testing.T) {
	tr := NewTracker()

	// No activities at all
	logs := tr.GetActivityByUser("unknown")
	assert.NotNil(t, logs)
	assert.Empty(t, logs)

	// Add for another user
	tr.LogActivity("user1", "login", nil)
	logs = tr.GetActivityByUser("unknown")
	assert.NotNil(t, logs)
	assert.Empty(t, logs)
}

func TestTracker_GetActivityByUser_ReturnsCopy(t *testing.T) {
	tr := NewTracker()
	tr.LogActivity("user1", "login", nil)

	logs := tr.GetActivityByUser("user1")
	assert.Len(t, logs, 1)

	// Mutate returned slice and ensure internal state not affected
	logs[0].Action = "modified"

	internal := tr.GetActivityByUser("user1")
	assert.Equal(t, "login", internal[0].Action)
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

	// User exists but no logs (should not happen with current API, but test anyway)
	tr.activities["user1"] = []ActivityLog{}
	stats = tr.GetActivityStats("user1")
	assert.NotNil(t, stats)
	assert.Equal(t, 0, stats.TotalActions)
	assert.Equal(t, 0, stats.UniqueActions)
	assert.NotNil(t, stats.ActionCounts)
	assert.Empty(t, stats.ActionCounts)
	assert.True(t, stats.FirstActivity.IsZero())
	assert.True(t, stats.LastActivity.IsZero())
	assert.Equal(t, "", stats.MostFrequent)
}

func TestTracker_GetActivityStats_WithLogs(t *testing.T) {
	tr := NewTracker()
	now := time.Now()

	// Manually control timestamps
	tr.activities["user1"] = []ActivityLog{
		{ID: "1", UserID: "user1", Action: "login", Timestamp: now.Add(-3 * time.Hour)},
		{ID: "2", UserID: "user1", Action: "view", Timestamp: now.Add(-2 * time.Hour)},
		{ID: "3", UserID: "user1", Action: "login", Timestamp: now.Add(-1 * time.Hour)},
	}

	stats := tr.GetActivityStats("user1")
	assert.Equal(t, 3, stats.TotalActions)
	assert.Equal(t, 2, stats.UniqueActions)
	assert.Equal(t, 2, stats.ActionCounts["login"])
	assert.Equal(t, 1, stats.ActionCounts["view"])
	assert.Equal(t, now.Add(-3*time.Hour), stats.FirstActivity)
	assert.Equal(t, now.Add(-1*time.Hour), stats.LastActivity)
	assert.Equal(t, "login", stats.MostFrequent)
}

func TestTracker_GetActivityByDateRange_NoUser(t *testing.T) {
	tr := NewTracker()
	start := time.Now().Add(-1 * time.Hour)
	end := time.Now()

	logs := tr.GetActivityByDateRange("unknown", start, end)
	assert.NotNil(t, logs)
	assert.Empty(t, logs)
}

func TestTracker_GetActivityByDateRange_Filtering(t *testing.T) {
	tr := NewTracker()
	now := time.Now()

	logs := []ActivityLog{
		{ID: "1", UserID: "user1", Action: "a1", Timestamp: now.Add(-3 * time.Hour)},
		{ID: "2", UserID: "user1", Action: "a2", Timestamp: now.Add(-2 * time.Hour)},
		{ID: "3", UserID: "user1", Action: "a3", Timestamp: now.Add(-1 * time.Hour)},
		{ID: "4", UserID: "user1", Action: "a4", Timestamp: now},
	}
	tr.activities["user1"] = logs

	tests := []struct {
		name    string
		start   time.Time
		end     time.Time
		wantIDs []string
	}{
		{
			name:    "all in range",
			start:   now.Add(-4 * time.Hour),
			end:     now.Add(1 * time.Hour),
			wantIDs: []string{"1", "2", "3", "4"},
		},
		{
			name:    "middle range",
			start:   now.Add(-2*time.Hour - time.Minute),
			end:     now.Add(-30 * time.Minute),
			wantIDs: []string{"2", "3"},
		},
		{
			name:    "single exact match start",
			start:   logs[1].Timestamp,
			end:     logs[1].Timestamp,
			wantIDs: []string{"2"},
		},
		{
			name:    "single exact match end",
			start:   logs[3].Timestamp,
			end:     logs[3].Timestamp,
			wantIDs: []string{"4"},
		},
		{
			name:    "none in range",
			start:   now.Add(1 * time.Hour),
			end:     now.Add(2 * time.Hour),
			wantIDs: []string{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := tr.GetActivityByDateRange("user1", tt.start, tt.end)
			assert.Len(t, got, len(tt.wantIDs))
			for i, id := range tt.wantIDs {
				assert.Equal(t, id, got[i].ID)
			}
		})
	}
}

func TestTracker_GetAllUsers_EmptyAndSorted(t *testing.T) {
	tr := NewTracker()

	users := tr.GetAllUsers()
	assert.NotNil(t, users)
	assert.Empty(t, users)

	tr.LogActivity("userB", "a1", nil)
	tr.LogActivity("userA", "a2", nil)
	tr.LogActivity("userC", "a3", nil)
	tr.LogActivity("userA", "a4", nil)

	users = tr.GetAllUsers()
	assert.Equal(t, []string{"userA", "userB", "userC"}, users)
}

func TestTracker_DeleteUserActivity_Behavior(t *testing.T) {
	tr := NewTracker()
	tr.LogActivity("user1", "a1", nil)
	tr.LogActivity("user2", "a2", nil)

	// Delete non-existing
	ok := tr.DeleteUserActivity("unknown")
	assert.False(t, ok)

	// Delete existing
	ok = tr.DeleteUserActivity("user1")
	assert.True(t, ok)

	// Ensure removed
	logs := tr.GetActivityByUser("user1")
	assert.Empty(t, logs)

	// Ensure other user unaffected
	logs = tr.GetActivityByUser("user2")
	assert.Len(t, logs, 1)
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

func TestFindMostFrequentAction_Empty(t *testing.T) {
	result := findMostFrequentAction(map[string]int{})
	assert.Equal(t, "", result)
}

func TestFindMostFrequentAction_SingleAndMultiple(t *testing.T) {
	tests := []struct {
		name   string
		input  map[string]int
		expect string
	}{
		{
			name:   "single action",
			input:  map[string]int{"login": 1},
			expect: "login",
		},
		{
			name:   "multiple actions",
			input:  map[string]int{"login": 2, "view": 5, "logout": 3},
			expect: "view",
		},
		{
			name:   "tie returns one of max (implementation-specific)",
			input:  map[string]int{"a": 3, "b": 3},
			expect: "", // we only assert it's one of the keys below
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := findMostFrequentAction(tt.input)
			if tt.expect != "" {
				assert.Equal(t, tt.expect, result)
			} else {
				// For tie case, ensure result is one of the keys with max count
				if len(tt.input) > 0 {
					max := 0
					for _, c := range tt.input {
						if c > max {
							max = c
						}
					}
					assert.NotEmpty(t, result)
					_, ok := tt.input[result]
					assert.True(t, ok)
					assert.Equal(t, max, tt.input[result])
				}
			}
		})
	}
}
