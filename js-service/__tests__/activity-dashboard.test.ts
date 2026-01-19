import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'
import { ActivityDashboard, Activity } from '../src/activity-dashboard'

describe('ActivityDashboard', () => {
  let activities: Activity[]
  let dashboard: ActivityDashboard

  const makeDate = (iso: string) => new Date(iso)

  beforeEach(() => {
    activities = [
      {
        id: '1',
        user_id: 'user1',
        action: 'login',
        timestamp: makeDate('2024-01-01T10:00:00Z'),
      },
      {
        id: '2',
        user_id: 'user1',
        action: 'view',
        timestamp: makeDate('2024-01-01T10:10:00Z'),
      },
      {
        id: '3',
        user_id: 'user1',
        action: 'view',
        timestamp: makeDate('2024-01-01T11:00:00Z'),
      },
      {
        id: '4',
        user_id: 'user1',
        action: 'logout',
        timestamp: makeDate('2024-01-02T09:00:00Z'),
      },
      {
        id: '5',
        user_id: 'user2',
        action: 'login',
        timestamp: makeDate('2024-01-01T12:00:00Z'),
      },
      {
        id: '6',
        user_id: 'user2',
        action: 'view',
        timestamp: makeDate('2024-01-03T12:00:00Z'),
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
      // first: 2024-01-01T10:00, last: 2024-01-02T09:00
      // diff ~23h < 24h => ceil(0.9583) = 1 day
      expect(result.actionsPerDay).toBe(4 / 1)
      expect(result.mostFrequentAction).toBe('view')
      // sessions: gap > 30 minutes between 10:10 and 11:00? 50 min -> new session
      // 10:00,10:10 (same session), 11:00 (new), 2024-01-02 09:00 (gap > 30m from 11:00 -> new)
      // sessions = 3, avg = 4/3 = 1.33
      expect(result.averageActionsPerSession).toBe(1.33)
    })

    it('handles single activity correctly', () => {
      const singleActivity: Activity = {
        id: '7',
        user_id: 'single',
        action: 'only',
        timestamp: makeDate('2024-01-10T00:00:00Z'),
      }
      const singleDashboard = new ActivityDashboard([singleActivity])
      const result = singleDashboard.getUserSummary('single')
      expect(result).not.toBeNull()
      if (!result) return

      expect(result.totalActions).toBe(1)
      expect(result.uniqueActions).toBe(1)
      expect(result.actionsPerDay).toBe(1)
      expect(result.mostFrequentAction).toBe('only')
      expect(result.averageActionsPerSession).toBe(1)
    })
  })

  describe('getActivityTrends', () => {
    it('returns empty array when user has no activities', () => {
      const result = dashboard.getActivityTrends('unknown')
      expect(result).toEqual([])
    })

    it('groups activities by day and calculates growth rate', () => {
      const result = dashboard.getActivityTrends('user2', 'day')
      // user2 has activities on 2024-01-01 and 2024-01-03
      expect(result.length).toBe(2)
      expect(result[0]).toEqual({
        period: '2024-01-01',
        count: 1,
        growthRate: 0,
      })
      expect(result[1].period).toBe('2024-01-03')
      expect(result[1].count).toBe(1)
      // previous count is 1, so growthRate = 0
      expect(result[1].growthRate).toBe(0)
    })

    it('groups activities by hour', () => {
      const result = dashboard.getActivityTrends('user1', 'hour')
      const periods = result.map(r => r.period)
      expect(periods).toContain('2024-01-01 10:00')
      expect(periods).toContain('2024-01-01 11:00')
      expect(periods).toContain('2024-01-02 09:00')

      const tenAm = result.find(r => r.period === '2024-01-01 10:00')
      expect(tenAm?.count).toBe(2)
      const elevenAm = result.find(r => r.period === '2024-01-01 11:00')
      expect(elevenAm?.count).toBe(1)
    })

    it('groups activities by week and month', () => {
      const weekTrends = dashboard.getActivityTrends('user1', 'week')
      expect(weekTrends.length).toBeGreaterThan(0)
      weekTrends.forEach(t => {
        expect(t.period).toMatch(/^\d{4}-W\d{2}$/)
      })

      const monthTrends = dashboard.getActivityTrends('user1', 'month')
      expect(monthTrends.length).toBe(1)
      expect(monthTrends[0].period).toBe('2024-01')
      expect(monthTrends[0].count).toBe(4)
    })
  })

  describe('filterByDateRange', () => {
    it('returns activities within inclusive date range for user', () => {
      const start = makeDate('2024-01-01T10:05:00Z')
      const end = makeDate('2024-01-01T23:59:59Z')
      const result = dashboard.filterByDateRange('user1', start, end)
      // user1 activities at 10:10, 11:00 on that day
      expect(result.map(a => a.id)).toEqual(['2', '3'])
    })

    it('returns empty array when no activities in range', () => {
      const start = makeDate('2025-01-01T00:00:00Z')
      const end = makeDate('2025-01-02T00:00:00Z')
      const result = dashboard.filterByDateRange('user1', start, end)
      expect(result).toEqual([])
    })

    it('filters by user id as well as date', () => {
      const start = makeDate('2024-01-01T00:00:00Z')
      const end = makeDate('2024-01-04T00:00:00Z')
      const resultUser1 = dashboard.filterByDateRange('user1', start, end)
      const resultUser2 = dashboard.filterByDateRange('user2', start, end)
      expect(resultUser1.every(a => a.user_id === 'user1')).toBe(true)
      expect(resultUser2.every(a => a.user_id === 'user2')).toBe(true)
    })
  })

  describe('aggregateByAction', () => {
    it('returns empty array when user has no activities', () => {
      const result = dashboard.aggregateByAction('unknown')
      expect(result).toEqual([])
    })

    it('aggregates counts, percentages and occurrence dates per action', () => {
      const result = dashboard.aggregateByAction('user1')
      // user1 actions: login(1), view(2), logout(1)
      expect(result.length).toBe(3)
      // sorted by count desc, so "view" first
      expect(result[0].action).toBe('view')
      expect(result[0].count).toBe(2)
      expect(result[0].percentage).toBe(parseFloat(((2 / 4) * 100).toFixed(2)))
      expect(result[0].firstOccurrence).toEqual(makeDate('2024-01-01T10:10:00Z'))
      expect(result[0].lastOccurrence).toEqual(makeDate('2024-01-01T11:00:00Z'))

      const loginGroup = result.find(g => g.action === 'login')
      expect(loginGroup?.count).toBe(1)
      expect(loginGroup?.percentage).toBe(25)
      expect(loginGroup?.firstOccurrence).toEqual(makeDate('2024-01-01T10:00:00Z'))
      expect(loginGroup?.lastOccurrence).toEqual(makeDate('2024-01-01T10:00:00Z'))
    })

    it('sorts groups by count descending', () => {
      const result = dashboard.aggregateByAction('user1')
      const counts = result.map(g => g.count)
      const sortedCounts = [...counts].sort((a, b) => b - a)
      expect(counts).toEqual(sortedCounts)
    })
  })

  describe('getTopActions_old', () => {
    it('returns all actions sorted by count when limit not applied', () => {
      const result = dashboard.getTopActions_old('user1')
      expect(result.length).toBe(3)
      expect(result[0].action).toBe('view')
      expect(result[0].count).toBe(2)
      expect(result[1].count).toBe(1)
      expect(result[2].count).toBe(1)
    })

    it('calculates percentages based on total actions', () => {
      const result = dashboard.getTopActions_old('user1')
      const total = 4
      result.forEach(group => {
        const expected = parseFloat(((group.count / total) * 100).toFixed(2))
        expect(group.percentage).toBe(expected)
      })
    })
  })

  describe('getTopActions', () => {
    it('returns top N actions using aggregateByAction', () => {
      const spy = jest.spyOn(ActivityDashboard.prototype as any, 'aggregateByAction')
      const result = dashboard.getTopActions('user1', 2)
      expect(spy).toHaveBeenCalledWith('user1')
      expect(result.length).toBe(2)
      expect(result[0].count).toBeGreaterThanOrEqual(result[1].count)
      spy.mockRestore()
    })

    it('defaults to limit 5 when not provided', () => {
      const result = dashboard.getTopActions('user1')
      // only 3 actions exist, so should return 3
      expect(result.length).toBe(3)
    })

    it('returns empty array when user has no activities', () => {
      const result = dashboard.getTopActions('unknown', 3)
      expect(result).toEqual([])
    })
  })

  describe('calculateEngagementScore', () => {
    it('returns 0 when user has no activities', () => {
      const result = dashboard.calculateEngagementScore('unknown')
      expect(result).toBe(0)
    })

    it('calculates engagement score based on summary metrics', () => {
      const summary = dashboard.getUserSummary('user1')
      expect(summary).not.toBeNull()
      if (!summary) return

      const volumeScore = Math.min(summary.totalActions / 100, 1) * 30
      const diversityScore = Math.min(summary.uniqueActions / 10, 1) * 30
      const frequencyScore = Math.min(summary.actionsPerDay / 5, 1) * 40
      const expected = parseFloat((volumeScore + diversityScore + frequencyScore).toFixed(2))

      const result = dashboard.calculateEngagementScore('user1')
      expect(result).toBe(expected)
    })

    it('caps each component score at its maximum', () => {
      const manyActivities: Activity[] = []
      for (let i = 0; i < 200; i++) {
        manyActivities.push({
          id: `m${i}`,
          user_id: 'heavy',
          action: `action${i % 20}`,
          timestamp: makeDate('2024-01-01T00:00:00Z'),
        })
      }
      const heavyDashboard = new ActivityDashboard(manyActivities)
      const score = heavyDashboard.calculateEngagementScore('heavy')
      // max volume 30, diversity 30, frequency 40 => 100
      expect(score).toBe(100)
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

    it('does not mutate original activities array when aggregating', () => {
      const original = [...activities]
      dashboard.aggregateByAction('user1')
      expect(activities).toEqual(original)
    })
  })
})