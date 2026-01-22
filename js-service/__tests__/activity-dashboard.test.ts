import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'
import { ActivityDashboard, Activity } from '../src/activity-dashboard'

describe('ActivityDashboard', () => {
  let activities: Activity[]
  let dashboard: ActivityDashboard

  beforeEach(() => {
    activities = [
      {
        id: '1',
        user_id: 'user1',
        action: 'login',
        timestamp: new Date('2024-01-01T10:00:00Z'),
      },
      {
        id: '2',
        user_id: 'user1',
        action: 'view',
        timestamp: new Date('2024-01-01T10:05:00Z'),
      },
      {
        id: '3',
        user_id: 'user1',
        action: 'view',
        timestamp: new Date('2024-01-02T11:00:00Z'),
      },
      {
        id: '4',
        user_id: 'user1',
        action: 'purchase',
        timestamp: new Date('2024-01-04T12:00:00Z'),
      },
      {
        id: '5',
        user_id: 'user2',
        action: 'login',
        timestamp: new Date('2024-01-01T09:00:00Z'),
      },
    ]
    dashboard = new ActivityDashboard(activities)
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  describe('getUserSummary', () => {
    it('returns null when user has no activities', () => {
      const result = dashboard.getUserSummary('unknown')
      expect(result).toBeNull()
    })

    it('calculates summary metrics correctly for a user', () => {
      const result = dashboard.getUserSummary('user1')
      expect(result).not.toBeNull()
      if (!result) return

      expect(result.totalActions).toBe(4)
      expect(result.uniqueActions).toBe(3)
      // first: 2024-01-01T10:00, last: 2024-01-04T12:00
      // diff ~ 3.0833 days -> ceil = 4 days
      // actionsPerDay = 4 / 4 = 1.00
      expect(result.actionsPerDay).toBe(1)
      expect(result.mostFrequentAction).toBe('view')
      // sessions: [10:00,10:05, next 11:00 next day (>30m), next 12:00 two days later (>30m)]
      // => 3 sessions, avg = 4/3 = 1.33
      expect(result.averageActionsPerSession).toBe(1.33)
    })

    it('handles single activity correctly', () => {
      const single = new ActivityDashboard([
        {
          id: '1',
          user_id: 'userX',
          action: 'login',
          timestamp: new Date('2024-01-10T10:00:00Z'),
        },
      ])
      const result = single.getUserSummary('userX')
      expect(result).not.toBeNull()
      if (!result) return

      expect(result.totalActions).toBe(1)
      expect(result.uniqueActions).toBe(1)
      // daysActive should be at least 1
      expect(result.actionsPerDay).toBe(1)
      expect(result.mostFrequentAction).toBe('login')
      expect(result.averageActionsPerSession).toBe(1)
    })
  })

  describe('getActivityTrends', () => {
    it('returns empty array when user has no activities', () => {
      const result = dashboard.getActivityTrends('unknown')
      expect(result).toEqual([])
    })

    it('groups activities by day and calculates growth rate', () => {
      const result = dashboard.getActivityTrends('user1', 'day')
      // user1 dates: 2024-01-01 (2), 2024-01-02 (1), 2024-01-04 (1)
      expect(result).toHaveLength(3)
      expect(result[0]).toEqual({ period: '2024-01-01', count: 2, growthRate: 0 })
      // growth from 2 to 1: ((1-2)/2)*100 = -50
      expect(result[1]).toEqual({ period: '2024-01-02', count: 1, growthRate: -50 })
      // growth from 1 to 1: 0
      expect(result[2]).toEqual({ period: '2024-01-04', count: 1, growthRate: 0 })
    })

    it('groups activities by hour', () => {
      const result = dashboard.getActivityTrends('user1', 'hour')
      const periods = result.map(r => r.period)
      expect(periods).toContain('2024-01-01 10:00')
      expect(periods).toContain('2024-01-02 11:00')
      expect(periods).toContain('2024-01-04 12:00')
      const first = result.find(r => r.period === '2024-01-01 10:00')
      expect(first?.count).toBe(2)
    })

    it('groups activities by month and week', () => {
      const byMonth = dashboard.getActivityTrends('user1', 'month')
      expect(byMonth).toHaveLength(1)
      expect(byMonth[0].period).toBe('2024-01')
      expect(byMonth[0].count).toBe(4)

      const byWeek = dashboard.getActivityTrends('user1', 'week')
      expect(byWeek.length).toBeGreaterThanOrEqual(1)
      const totalCount = byWeek.reduce((sum, r) => sum + r.count, 0)
      expect(totalCount).toBe(4)
    })
  })

  describe('filterByDateRange', () => {
    it('returns activities within inclusive date range for user', () => {
      const start = new Date('2024-01-01T10:00:00Z')
      const end = new Date('2024-01-02T23:59:59Z')
      const result = dashboard.filterByDateRange('user1', start, end)
      // user1 activities on 1st and 2nd: 3
      expect(result).toHaveLength(3)
      expect(result.every(a => a.user_id === 'user1')).toBe(true)
      expect(result.map(a => a.id)).toEqual(['1', '2', '3'])
    })

    it('returns empty array when no activities in range', () => {
      const start = new Date('2025-01-01T00:00:00Z')
      const end = new Date('2025-01-02T00:00:00Z')
      const result = dashboard.filterByDateRange('user1', start, end)
      expect(result).toEqual([])
    })

    it('respects inclusive boundaries', () => {
      const exactStart = new Date('2024-01-01T10:00:00Z')
      const exactEnd = new Date('2024-01-01T10:05:00Z')
      const result = dashboard.filterByDateRange('user1', exactStart, exactEnd)
      expect(result.map(a => a.id)).toEqual(['1', '2'])
    })
  })

  describe('aggregateByAction', () => {
    it('returns empty array when user has no activities', () => {
      const result = dashboard.aggregateByAction('unknown')
      expect(result).toEqual([])
    })

    it('aggregates actions with counts, percentages and occurrences', () => {
      const result = dashboard.aggregateByAction('user1')
      // actions: login(1), view(2), purchase(1) -> sorted by count desc
      expect(result).toHaveLength(3)
      expect(result[0].action).toBe('view')
      expect(result[0].count).toBe(2)
      expect(result[0].percentage).toBe(50)
      expect(result[1].action).toBe('login')
      expect(result[1].count).toBe(1)
      expect(result[1].percentage).toBe(25)
      expect(result[2].action).toBe('purchase')
      expect(result[2].count).toBe(1)
      expect(result[2].percentage).toBe(25)

      const viewGroup = result.find(g => g.action === 'view')
      expect(viewGroup?.firstOccurrence.getTime()).toBe(
        new Date('2024-01-01T10:05:00Z').getTime()
      )
      expect(viewGroup?.lastOccurrence.getTime()).toBe(
        new Date('2024-01-02T11:00:00Z').getTime()
      )
    })

    it('sorts groups by count descending', () => {
      const custom = new ActivityDashboard([
        {
          id: '1',
          user_id: 'u',
          action: 'a',
          timestamp: new Date('2024-01-01T00:00:00Z'),
        },
        {
          id: '2',
          user_id: 'u',
          action: 'b',
          timestamp: new Date('2024-01-01T01:00:00Z'),
        },
        {
          id: '3',
          user_id: 'u',
          action: 'b',
          timestamp: new Date('2024-01-01T02:00:00Z'),
        },
      ])
      const result = custom.aggregateByAction('u')
      expect(result.map(g => g.action)).toEqual(['b', 'a'])
    })
  })

  describe('getTopActions_old', () => {
    it('returns all actions sorted by count when limit not applied', () => {
      const result = dashboard.getTopActions_old('user1')
      expect(result).toHaveLength(3)
      expect(result[0].action).toBe('view')
      expect(result[0].count).toBe(2)
      expect(result[1].action).toBe('login')
      expect(result[2].action).toBe('purchase')
    })

    it('calculates percentages based on total actions', () => {
      const result = dashboard.getTopActions_old('user1')
      const total = 4
      const view = result.find(r => r.action === 'view')
      const login = result.find(r => r.action === 'login')
      expect(view?.percentage).toBe(parseFloat(((2 / total) * 100).toFixed(2)))
      expect(login?.percentage).toBe(parseFloat(((1 / total) * 100).toFixed(2)))
    })
  })

  describe('getTopActions', () => {
    it('returns limited number of top actions', () => {
      const result = dashboard.getTopActions('user1', 2)
      expect(result).toHaveLength(2)
      expect(result[0].action).toBe('view')
      expect(result[1].action).toBe('login')
    })

    it('defaults limit to 5 and returns all when fewer actions', () => {
      const result = dashboard.getTopActions('user1')
      expect(result).toHaveLength(3)
    })

    it('returns empty array when user has no activities', () => {
      const result = dashboard.getTopActions('unknown')
      expect(result).toEqual([])
    })
  })

  describe('calculateEngagementScore', () => {
    it('returns 0 when user has no activities', () => {
      const result = dashboard.calculateEngagementScore('unknown')
      expect(result).toBe(0)
    })

    it('calculates engagement score based on summary metrics', () => {
      const result = dashboard.calculateEngagementScore('user1')
      const summary = dashboard.getUserSummary('user1')
      if (!summary) throw new Error('summary should exist')

      const volumeScore = Math.min(summary.totalActions / 100, 1) * 30
      const diversityScore = Math.min(summary.uniqueActions / 10, 1) * 30
      const frequencyScore = Math.min(summary.actionsPerDay / 5, 1) * 40
      const expected = parseFloat((volumeScore + diversityScore + frequencyScore).toFixed(2))

      expect(result).toBe(expected)
    })

    it('caps each component score at its maximum', () => {
      const manyActivities: Activity[] = []
      for (let i = 0; i < 200; i++) {
        manyActivities.push({
          id: `a${i}`,
          user_id: 'heavy',
          action: `action${i % 20}`,
          timestamp: new Date('2024-01-01T00:00:00Z'),
        })
      }
      const heavyDashboard = new ActivityDashboard(manyActivities)
      const score = heavyDashboard.calculateEngagementScore('heavy')
      // All components should be capped, so score should be <= 100
      expect(score).toBeLessThanOrEqual(100)
    })
  })

  describe('constructor and basic behavior', () => {
    it('initializes with empty activities when none provided', () => {
      const emptyDashboard = new ActivityDashboard()
      const summary = emptyDashboard.getUserSummary('any')
      expect(summary).toBeNull()
      const trends = emptyDashboard.getActivityTrends('any')
      expect(trends).toEqual([])
    })

    it('does not mix activities between users', () => {
      const user1Summary = dashboard.getUserSummary('user1')
      const user2Summary = dashboard.getUserSummary('user2')
      expect(user1Summary?.totalActions).toBe(4)
      expect(user2Summary?.totalActions).toBe(1)
    })
  })
})