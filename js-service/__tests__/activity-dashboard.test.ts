import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'
import { ActivityDashboard, Activity } from '../src/activity-dashboard'

describe('ActivityDashboard', () => {
  let baseDate: Date
  let activities: Activity[]
  let dashboard: ActivityDashboard

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
        timestamp: new Date(baseDate.getTime() + 2 * 60 * 60 * 1000) // +2 hours (new session)
      },
      {
        id: '6',
        user_id: 'user2',
        action: 'login',
        timestamp: new Date(baseDate.getTime())
      }
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

      expect(result.totalActions).toBe(5)
      expect(result.uniqueActions).toBe(3)
      expect(result.mostFrequentAction).toBe('view')

      // All actions for user1 are within same day, so daysActive = 1
      expect(result.actionsPerDay).toBe(5.0)

      // Sessions: first 4 actions within 40 minutes, last action 2h after first -> gap 80min > 30 -> 2 sessions
      // average = 5 / 2 = 2.5, rounded to 2 decimals
      expect(result.averageActionsPerSession).toBe(2.5)
    })

    it('handles single activity correctly', () => {
      const singleActivity: Activity = {
        id: '7',
        user_id: 'single',
        action: 'login',
        timestamp: new Date(baseDate.getTime())
      }
      const singleDashboard = new ActivityDashboard([singleActivity])

      const result = singleDashboard.getUserSummary('single')
      expect(result).not.toBeNull()
      if (!result) return

      expect(result.totalActions).toBe(1)
      expect(result.uniqueActions).toBe(1)
      expect(result.mostFrequentAction).toBe('login')
      expect(result.actionsPerDay).toBe(1)
      expect(result.averageActionsPerSession).toBe(1)
    })

    it('uses at least 1 day when first and last activity are same timestamp', () => {
      const sameTime = new Date('2024-01-01T12:00:00.000Z')
      const acts: Activity[] = [
        { id: '1', user_id: 'u', action: 'a', timestamp: sameTime },
        { id: '2', user_id: 'u', action: 'b', timestamp: sameTime }
      ]
      const d = new ActivityDashboard(acts)

      const result = d.getUserSummary('u')
      expect(result).not.toBeNull()
      if (!result) return

      expect(result.totalActions).toBe(2)
      expect(result.actionsPerDay).toBe(2)
    })
  })

  describe('getActivityTrends', () => {
    it('returns empty array when user has no activities', () => {
      const result = dashboard.getActivityTrends('unknown')
      expect(result).toEqual([])
    })

    it('groups activities by day and calculates growth rate', () => {
      const extraActivities: Activity[] = [
        {
          id: '7',
          user_id: 'user1',
          action: 'login',
          timestamp: new Date('2024-01-02T01:00:00.000Z')
        },
        {
          id: '8',
          user_id: 'user1',
          action: 'view',
          timestamp: new Date('2024-01-02T02:00:00.000Z')
        }
      ]
      const d = new ActivityDashboard([...activities, ...extraActivities])

      const result = d.getActivityTrends('user1', 'day')
      expect(result.length).toBe(2)

      const day1 = result[0]
      const day2 = result[1]

      expect(day1.period).toBe('2024-01-01')
      expect(day1.count).toBe(5)
      expect(day1.growthRate).toBe(0)

      expect(day2.period).toBe('2024-01-02')
      expect(day2.count).toBe(2)
      const expectedGrowth = parseFloat((((2 - 5) / 5) * 100).toFixed(2))
      expect(day2.growthRate).toBe(expectedGrowth)
    })

    it('groups activities by hour when periodType is hour', () => {
      const d = new ActivityDashboard(activities.filter(a => a.user_id === 'user1'))
      const result = d.getActivityTrends('user1', 'hour')

      const periods = result.map(r => r.period)
      expect(periods.every(p => p.includes(':00'))).toBe(true)
      expect(result.reduce((sum, r) => sum + r.count, 0)).toBe(5)
    })

    it('groups activities by week and month', () => {
      const d = new ActivityDashboard(activities.filter(a => a.user_id === 'user1'))
      const weekTrends = d.getActivityTrends('user1', 'week')
      const monthTrends = d.getActivityTrends('user1', 'month')

      expect(weekTrends.length).toBe(1)
      expect(weekTrends[0].count).toBe(5)
      expect(weekTrends[0].period.startsWith('2024-W')).toBe(true)

      expect(monthTrends.length).toBe(1)
      expect(monthTrends[0].count).toBe(5)
      expect(monthTrends[0].period).toBe('2024-01')
    })
  })

  describe('filterByDateRange', () => {
    it('returns activities within inclusive date range for a user', () => {
      const start = new Date(baseDate.getTime() + 10 * 60 * 1000)
      const end = new Date(baseDate.getTime() + 40 * 60 * 1000)

      const result = dashboard.filterByDateRange('user1', start, end)
      const ids = result.map(a => a.id).sort()

      expect(ids).toEqual(['2', '3', '4'])
    })

    it('returns empty array when no activities in range', () => {
      const start = new Date(baseDate.getTime() + 24 * 60 * 60 * 1000)
      const end = new Date(baseDate.getTime() + 48 * 60 * 60 * 1000)

      const result = dashboard.filterByDateRange('user1', start, end)
      expect(result).toEqual([])
    })

    it('filters by userId as well as date range', () => {
      const start = new Date(baseDate.getTime() - 60 * 60 * 1000)
      const end = new Date(baseDate.getTime() + 60 * 60 * 1000)

      const resultUser1 = dashboard.filterByDateRange('user1', start, end)
      const resultUser2 = dashboard.filterByDateRange('user2', start, end)

      expect(resultUser1.length).toBe(4)
      expect(resultUser2.length).toBe(1)
      expect(resultUser2[0].user_id).toBe('user2')
    })
  })

  describe('aggregateByAction', () => {
    it('returns empty array when user has no activities', () => {
      const result = dashboard.aggregateByAction('unknown')
      expect(result).toEqual([])
    })

    it('aggregates actions with counts, percentages and occurrences', () => {
      const result = dashboard.aggregateByAction('user1')

      expect(result.length).toBe(3)
      expect(result[0].count).toBeGreaterThanOrEqual(result[1].count)

      const loginGroup = result.find(g => g.action === 'login')
      const viewGroup = result.find(g => g.action === 'view')
      const purchaseGroup = result.find(g => g.action === 'purchase')

      expect(loginGroup).toBeDefined()
      expect(viewGroup).toBeDefined()
      expect(purchaseGroup).toBeDefined()

      if (!loginGroup || !viewGroup || !purchaseGroup) return

      expect(loginGroup.count).toBe(2)
      expect(viewGroup.count).toBe(2)
      expect(purchaseGroup.count).toBe(1)

      const total = 5
      expect(loginGroup.percentage).toBe(parseFloat(((2 / total) * 100).toFixed(2)))
      expect(viewGroup.percentage).toBe(parseFloat(((2 / total) * 100).toFixed(2)))
      expect(purchaseGroup.percentage).toBe(parseFloat(((1 / total) * 100).toFixed(2)))

      expect(loginGroup.firstOccurrence <= loginGroup.lastOccurrence).toBe(true)
      expect(viewGroup.firstOccurrence <= viewGroup.lastOccurrence).toBe(true)
      expect(purchaseGroup.firstOccurrence <= purchaseGroup.lastOccurrence).toBe(true)
    })

    it('sorts groups by count descending', () => {
      const acts: Activity[] = [
        { id: '1', user_id: 'u', action: 'a', timestamp: new Date('2024-01-01T00:00:00Z') },
        { id: '2', user_id: 'u', action: 'b', timestamp: new Date('2024-01-01T01:00:00Z') },
        { id: '3', user_id: 'u', action: 'b', timestamp: new Date('2024-01-01T02:00:00Z') },
        { id: '4', user_id: 'u', action: 'c', timestamp: new Date('2024-01-01T03:00:00Z') },
        { id: '5', user_id: 'u', action: 'c', timestamp: new Date('2024-01-01T04:00:00Z') },
        { id: '6', user_id: 'u', action: 'c', timestamp: new Date('2024-01-01T05:00:00Z') }
      ]
      const d = new ActivityDashboard(acts)

      const result = d.aggregateByAction('u')
      expect(result.map(g => g.action)).toEqual(['c', 'b', 'a'])
    })
  })

  describe('getTopActions_old', () => {
    it('returns all actions sorted by count when limit not applied', () => {
      const result = dashboard.getTopActions_old('user1')

      expect(result.length).toBe(3)
      const counts = result.map(r => r.count)
      expect(counts).toEqual([2, 2, 1])

      const total = 5
      expect(result[0].percentage).toBe(parseFloat(((result[0].count / total) * 100).toFixed(2)))
    })

    it('calculates first and last occurrence correctly', () => {
      const result = dashboard.getTopActions_old('user1')
      const loginGroup = result.find(r => r.action === 'login')
      expect(loginGroup).toBeDefined()
      if (!loginGroup) return

      expect(loginGroup.firstOccurrence.getTime()).toBe(activities[0].timestamp.getTime())
      expect(loginGroup.lastOccurrence.getTime()).toBe(activities[4].timestamp.getTime())
    })
  })

  describe('getTopActions', () => {
    it('returns top N actions based on aggregateByAction', () => {
      const spy = jest.spyOn(dashboard as any, 'aggregateByAction')
      const result = dashboard.getTopActions('user1', 2)

      expect(spy).toHaveBeenCalledWith('user1')
      expect(result.length).toBe(2)
    })

    it('defaults limit to 5 when not provided', () => {
      const result = dashboard.getTopActions('user1')
      expect(result.length).toBeLessThanOrEqual(5)
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
      if (!summary) return

      const volumeScore = Math.min(summary.totalActions / 100, 1) * 30
      const diversityScore = Math.min(summary.uniqueActions / 10, 1) * 30
      const frequencyScore = Math.min(summary.actionsPerDay / 5, 1) * 40
      const expected = parseFloat((volumeScore + diversityScore + frequencyScore).toFixed(2))

      expect(result).toBe(expected)
    })

    it('caps each component of engagement score at its maximum', () => {
      const manyActivities: Activity[] = []
      const userId = 'heavy'
      for (let i = 0; i < 200; i++) {
        manyActivities.push({
          id: `h-${i}`,
          user_id: userId,
          action: `action-${i % 20}`,
          timestamp: new Date(baseDate.getTime() + i * 60 * 1000)
        })
      }
      const d = new ActivityDashboard(manyActivities)

      const score = d.calculateEngagementScore(userId)
      expect(score).toBeLessThanOrEqual(100)
    })
  })
})