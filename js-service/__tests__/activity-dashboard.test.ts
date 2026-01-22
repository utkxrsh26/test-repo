import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'
import { ActivityDashboard, Activity } from '../src/activity-dashboard'

describe('ActivityDashboard', () => {
  let baseDate: Date
  let activities: Activity[]

  beforeEach(() => {
    baseDate = new Date('2024-01-01T00:00:00.000Z')

    activities = [
      {
        id: '1',
        user_id: 'user1',
        action: 'login',
        timestamp: new Date(baseDate.getTime())
      },
      {
        id: '2',
        user_id: 'user1',
        action: 'view',
        timestamp: new Date(baseDate.getTime() + 10 * 60 * 1000) // +10 min
      },
      {
        id: '3',
        user_id: 'user1',
        action: 'view',
        timestamp: new Date(baseDate.getTime() + 20 * 60 * 1000) // +20 min
      },
      {
        id: '4',
        user_id: 'user1',
        action: 'purchase',
        timestamp: new Date(baseDate.getTime() + 40 * 60 * 1000) // +40 min
      },
      {
        id: '5',
        user_id: 'user1',
        action: 'login',
        timestamp: new Date(baseDate.getTime() + 2 * 24 * 60 * 60 * 1000) // +2 days
      },
      {
        id: '6',
        user_id: 'user2',
        action: 'login',
        timestamp: new Date(baseDate.getTime() + 5 * 60 * 1000) // +5 min
      }
    ]
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  describe('getUserSummary', () => {
    it('returns null when user has no activities', () => {
      const dashboard = new ActivityDashboard(activities)
      const summary = dashboard.getUserSummary('unknown')

      expect(summary).toBeNull()
    })

    it('calculates summary metrics correctly for a user', () => {
      const dashboard = new ActivityDashboard(activities)
      const summary = dashboard.getUserSummary('user1')

      expect(summary).not.toBeNull()
      if (!summary) return

      // totalActions: all activities for user1
      expect(summary.totalActions).toBe(5)

      // uniqueActions: login, view, purchase
      expect(summary.uniqueActions).toBe(3)

      // daysActive: from first to last activity
      const first = activities.filter(a => a.user_id === 'user1').sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())[0].timestamp
      const last = activities.filter(a => a.user_id === 'user1').sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime()).slice(-1)[0].timestamp
      const diffMs = last.getTime() - first.getTime()
      const daysActive = Math.max(Math.ceil(diffMs / (1000 * 60 * 60 * 24)), 1)
      const expectedActionsPerDay = parseFloat((summary.totalActions / daysActive).toFixed(2))

      expect(summary.actionsPerDay).toBe(expectedActionsPerDay)

      // mostFrequentAction: 'view' appears twice, others once
      expect(summary.mostFrequentAction).toBe('view')

      // averageActionsPerSession: based on 30-minute gaps
      // user1 timestamps: 0, 10, 20, 40 minutes, then +2 days
      // gaps: 10, 10, 20, then large gap > 30 => 2 sessions
      const expectedAvgPerSession = parseFloat((5 / 2).toFixed(2))
      expect(summary.averageActionsPerSession).toBe(expectedAvgPerSession)
    })

    it('handles single activity correctly (daysActive minimum 1)', () => {
      const singleActivity: Activity[] = [
        {
          id: '1',
          user_id: 'userX',
          action: 'login',
          timestamp: new Date('2024-01-10T12:00:00.000Z')
        }
      ]
      const dashboard = new ActivityDashboard(singleActivity)
      const summary = dashboard.getUserSummary('userX')

      expect(summary).not.toBeNull()
      if (!summary) return

      expect(summary.totalActions).toBe(1)
      expect(summary.uniqueActions).toBe(1)
      expect(summary.actionsPerDay).toBe(1) // 1 action / 1 day
      expect(summary.mostFrequentAction).toBe('login')
      expect(summary.averageActionsPerSession).toBe(1) // 1 action in 1 session
    })
  })

  describe('getActivityTrends', () => {
    it('returns empty array when user has no activities', () => {
      const dashboard = new ActivityDashboard(activities)
      const trends = dashboard.getActivityTrends('unknown')

      expect(trends).toEqual([])
    })

    it('groups activities by day and calculates growth rate', () => {
      const userActivities: Activity[] = [
        {
          id: '1',
          user_id: 'user1',
          action: 'a',
          timestamp: new Date('2024-01-01T10:00:00.000Z')
        },
        {
          id: '2',
          user_id: 'user1',
          action: 'b',
          timestamp: new Date('2024-01-01T12:00:00.000Z')
        },
        {
          id: '3',
          user_id: 'user1',
          action: 'c',
          timestamp: new Date('2024-01-02T09:00:00.000Z')
        },
        {
          id: '4',
          user_id: 'user1',
          action: 'd',
          timestamp: new Date('2024-01-02T11:00:00.000Z')
        },
        {
          id: '5',
          user_id: 'user1',
          action: 'e',
          timestamp: new Date('2024-01-02T13:00:00.000Z')
        }
      ]
      const dashboard = new ActivityDashboard(userActivities)
      const trends = dashboard.getActivityTrends('user1', 'day')

      expect(trends).toHaveLength(2)
      expect(trends[0]).toEqual({
        period: '2024-01-01',
        count: 2,
        growthRate: 0
      })
      // growthRate = ((3 - 2) / 2) * 100 = 50
      expect(trends[1].period).toBe('2024-01-02')
      expect(trends[1].count).toBe(3)
      expect(trends[1].growthRate).toBe(50)
    })

    it('groups activities by hour when periodType is hour', () => {
      const userActivities: Activity[] = [
        {
          id: '1',
          user_id: 'user1',
          action: 'a',
          timestamp: new Date('2024-01-01T10:15:00.000Z')
        },
        {
          id: '2',
          user_id: 'user1',
          action: 'b',
          timestamp: new Date('2024-01-01T10:45:00.000Z')
        },
        {
          id: '3',
          user_id: 'user1',
          action: 'c',
          timestamp: new Date('2024-01-01T11:00:00.000Z')
        }
      ]
      const dashboard = new ActivityDashboard(userActivities)
      const trends = dashboard.getActivityTrends('user1', 'hour')

      expect(trends).toHaveLength(2)
      expect(trends[0].period).toBe('2024-01-01 10:00')
      expect(trends[0].count).toBe(2)
      expect(trends[1].period).toBe('2024-01-01 11:00')
      expect(trends[1].count).toBe(1)
    })

    it('groups activities by week and month correctly', () => {
      const userActivities: Activity[] = [
        {
          id: '1',
          user_id: 'user1',
          action: 'a',
          timestamp: new Date('2024-01-03T00:00:00.000Z')
        },
        {
          id: '2',
          user_id: 'user1',
          action: 'b',
          timestamp: new Date('2024-01-10T00:00:00.000Z')
        },
        {
          id: '3',
          user_id: 'user1',
          action: 'c',
          timestamp: new Date('2024-02-01T00:00:00.000Z')
        }
      ]
      const dashboard = new ActivityDashboard(userActivities)

      const weekTrends = dashboard.getActivityTrends('user1', 'week')
      expect(weekTrends.length).toBeGreaterThanOrEqual(2)
      expect(weekTrends[0].period.startsWith('2024-W')).toBe(true)

      const monthTrends = dashboard.getActivityTrends('user1', 'month')
      expect(monthTrends).toEqual([
        { period: '2024-01', count: 2, growthRate: 0 },
        { period: '2024-02', count: 1, growthRate: parseFloat((((1 - 2) / 2) * 100).toFixed(2)) }
      ])
    })
  })

  describe('filterByDateRange', () => {
    it('returns only activities for given user within date range', () => {
      const dashboard = new ActivityDashboard(activities)
      const start = new Date(baseDate.getTime() + 15 * 60 * 1000) // +15 min
      const end = new Date(baseDate.getTime() + 45 * 60 * 1000) // +45 min

      const result = dashboard.filterByDateRange('user1', start, end)

      // user1 activities at 20 and 40 minutes should be included
      expect(result.map(a => a.id)).toEqual(['3', '4'])
    })

    it('returns empty array when no activities in range', () => {
      const dashboard = new ActivityDashboard(activities)
      const start = new Date(baseDate.getTime() + 3 * 24 * 60 * 60 * 1000) // +3 days
      const end = new Date(baseDate.getTime() + 4 * 24 * 60 * 60 * 1000) // +4 days

      const result = dashboard.filterByDateRange('user1', start, end)

      expect(result).toEqual([])
    })
  })

  describe('aggregateByAction', () => {
    it('returns empty array when user has no activities', () => {
      const dashboard = new ActivityDashboard(activities)
      const result = dashboard.aggregateByAction('unknown')

      expect(result).toEqual([])
    })

    it('aggregates actions with counts, percentages and occurrences', () => {
      const dashboard = new ActivityDashboard(activities)
      const result = dashboard.aggregateByAction('user1')

      // user1 actions: login x2, view x2, purchase x1
      expect(result).toHaveLength(3)

      // sorted by count descending
      expect(result[0].action).toBe('login')
      expect(result[0].count).toBe(2)
      expect(result[1].action).toBe('view')
      expect(result[1].count).toBe(2)
      expect(result[2].action).toBe('purchase')
      expect(result[2].count).toBe(1)

      const total = 5
      const loginGroup = result.find(g => g.action === 'login')!
      const viewGroup = result.find(g => g.action === 'view')!
      const purchaseGroup = result.find(g => g.action === 'purchase')!

      expect(loginGroup.percentage).toBe(parseFloat(((2 / total) * 100).toFixed(2)))
      expect(viewGroup.percentage).toBe(parseFloat(((2 / total) * 100).toFixed(2)))
      expect(purchaseGroup.percentage).toBe(parseFloat(((1 / total) * 100).toFixed(2)))

      // first and last occurrence timestamps should match sorted activities per action
      const loginActivities = activities.filter(a => a.user_id === 'user1' && a.action === 'login').sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
      expect(loginGroup.firstOccurrence.getTime()).toBe(loginActivities[0].timestamp.getTime())
      expect(loginGroup.lastOccurrence.getTime()).toBe(loginActivities[loginActivities.length - 1].timestamp.getTime())
    })
  })

  describe('getTopActions_old', () => {
    it('returns all actions sorted by count without applying limit', () => {
      const dashboard = new ActivityDashboard(activities)
      const result = dashboard.getTopActions_old('user1', 1)

      // Should ignore limit and return all groups
      expect(result).toHaveLength(3)
      expect(result[0].count).toBeGreaterThanOrEqual(result[1].count)
      expect(result[1].count).toBeGreaterThanOrEqual(result[2].count)
    })

    it('calculates percentages based on total actions', () => {
      const dashboard = new ActivityDashboard(activities)
      const result = dashboard.getTopActions_old('user1')

      const total = 5
      const loginGroup = result.find(g => g.action === 'login')!
      expect(loginGroup.percentage).toBe(parseFloat(((2 / total) * 100).toFixed(2)))
    })
  })

  describe('getTopActions', () => {
    it('returns limited number of top actions using aggregateByAction', () => {
      const dashboard = new ActivityDashboard(activities)
      const result = dashboard.getTopActions('user1', 2)

      expect(result).toHaveLength(2)
      // Should be the two most frequent actions
      expect(result[0].count).toBeGreaterThanOrEqual(result[1].count)
    })

    it('returns all actions when limit exceeds available groups', () => {
      const dashboard = new ActivityDashboard(activities)
      const result = dashboard.getTopActions('user1', 10)

      expect(result).toHaveLength(3)
    })
  })

  describe('calculateEngagementScore', () => {
    it('returns 0 when user has no activities', () => {
      const dashboard = new ActivityDashboard(activities)
      const score = dashboard.calculateEngagementScore('unknown')

      expect(score).toBe(0)
    })

    it('calculates engagement score based on summary metrics', () => {
      const dashboard = new ActivityDashboard(activities)
      const summary = dashboard.getUserSummary('user1')
      if (!summary) throw new Error('Expected summary for user1')

      const volumeScore = Math.min(summary.totalActions / 100, 1) * 30
      const diversityScore = Math.min(summary.uniqueActions / 10, 1) * 30
      const frequencyScore = Math.min(summary.actionsPerDay / 5, 1) * 40
      const expectedScore = parseFloat((volumeScore + diversityScore + frequencyScore).toFixed(2))

      const score = dashboard.calculateEngagementScore('user1')
      expect(score).toBe(expectedScore)
    })

    it('caps each component of engagement score at its maximum', () => {
      const manyActivities: Activity[] = []
      const userId = 'heavyUser'
      const start = new Date('2024-01-01T00:00:00.000Z').getTime()

      // Create 200 actions over 5 days with many unique actions
      for (let i = 0; i < 200; i++) {
        manyActivities.push({
          id: String(i),
          user_id: userId,
          action: `action${i % 20}`, // 20 unique actions
          timestamp: new Date(start + i * 60 * 60 * 1000) // hourly
        })
      }

      const dashboard = new ActivityDashboard(manyActivities)
      const score = dashboard.calculateEngagementScore(userId)

      // All components should be capped, so score should be 30 + 30 + 40 = 100
      expect(score).toBe(100)
    })
  })

  describe('constructor and basic behavior', () => {
    it('initializes with empty activities when none provided', () => {
      const dashboard = new ActivityDashboard()
      const summary = dashboard.getUserSummary('any')

      expect(summary).toBeNull()
      const trends = dashboard.getActivityTrends('any')
      expect(trends).toEqual([])
    })

    it('does not mutate original activities array when performing operations', () => {
      const original = [...activities]
      const dashboard = new ActivityDashboard(activities)

      dashboard.getUserSummary('user1')
      dashboard.getActivityTrends('user1')
      dashboard.aggregateByAction('user1')
      dashboard.getTopActions('user1')

      expect(activities).toEqual(original)
    })
  })
})