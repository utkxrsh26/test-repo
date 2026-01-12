import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'
import { ActivityDashboard, Activity } from '../src/activity-dashboard'

describe('ActivityDashboard', () => {
  let activities: Activity[]
  let dashboard: ActivityDashboard

  beforeEach(() => {
    const base = new Date('2024-01-01T00:00:00Z')

    activities = [
      {
        id: '1',
        user_id: 'user1',
        action: 'login',
        timestamp: new Date(base.getTime())
      },
      {
        id: '2',
        user_id: 'user1',
        action: 'view',
        timestamp: new Date(base.getTime() + 60 * 60 * 1000) // +1h
      },
      {
        id: '3',
        user_id: 'user1',
        action: 'view',
        timestamp: new Date(base.getTime() + 2 * 60 * 60 * 1000) // +2h
      },
      {
        id: '4',
        user_id: 'user1',
        action: 'purchase',
        timestamp: new Date(base.getTime() + 26 * 60 * 60 * 1000) // +26h (next day +2h)
      },
      {
        id: '5',
        user_id: 'user2',
        action: 'login',
        timestamp: new Date(base.getTime() + 3 * 60 * 60 * 1000)
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

      // totalActions: 4 activities for user1
      expect(result.totalActions).toBe(4)

      // uniqueActions: login, view, purchase
      expect(result.uniqueActions).toBe(3)

      // daysActive: from 0h to 26h => ceil(26/24)=2
      // actionsPerDay: 4 / 2 = 2.00
      expect(result.actionsPerDay).toBe(2)

      // mostFrequentAction: 'view' (2 times)
      expect(result.mostFrequentAction).toBe('view')

      // averageActionsPerSession:
      // timestamps: 0h,1h,2h,26h; gaps: 1h,1h,24h -> last gap >30min => 2 sessions
      // 4 actions / 2 sessions = 2.00
      expect(result.averageActionsPerSession).toBe(2)
    })

    it('handles single activity correctly', () => {
      const singleActivity: Activity = {
        id: '10',
        user_id: 'single',
        action: 'only',
        timestamp: new Date('2024-01-01T10:00:00Z')
      }
      const singleDashboard = new ActivityDashboard([singleActivity])

      const result = singleDashboard.getUserSummary('single')
      expect(result).not.toBeNull()
      if (!result) return

      expect(result.totalActions).toBe(1)
      expect(result.uniqueActions).toBe(1)
      // daysActive: diff 0 => Math.ceil(0) = 0, then max(0,1)=1
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
      const result = dashboard.getActivityTrends('user1', 'day')
      // user1 has 3 activities on 2024-01-01 and 1 on 2024-01-02
      expect(result.length).toBe(2)

      const first = result[0]
      const second = result[1]

      expect(first.period).toBe('2024-01-01')
      expect(first.count).toBe(3)
      expect(first.growthRate).toBe(0)

      expect(second.period).toBe('2024-01-02')
      expect(second.count).toBe(1)
      // growthRate = ((1-3)/3)*100 = -66.666... => -66.67
      expect(second.growthRate).toBe(-66.67)
    })

    it('groups activities by hour', () => {
      const result = dashboard.getActivityTrends('user1', 'hour')
      // user1 has activities at 0h,1h,2h on day1 and 2h on day2
      const periods = result.map(r => r.period)
      expect(periods).toContain('2024-01-01 00:00')
      expect(periods).toContain('2024-01-01 01:00')
      expect(periods).toContain('2024-01-01 02:00')
      expect(periods).toContain('2024-01-02 02:00')

      const zeroHour = result.find(r => r.period === '2024-01-01 00:00')
      expect(zeroHour?.count).toBe(1)
    })

    it('groups activities by month and week using default sorting', () => {
      const monthTrends = dashboard.getActivityTrends('user1', 'month')
      expect(monthTrends.length).toBe(1)
      expect(monthTrends[0].period).toBe('2024-01')
      expect(monthTrends[0].count).toBe(4)

      const weekTrends = dashboard.getActivityTrends('user1', 'week')
      expect(weekTrends.length).toBe(1)
      expect(weekTrends[0].period.startsWith('2024-W')).toBe(true)
      expect(weekTrends[0].count).toBe(4)
    })
  })

  describe('filterByDateRange', () => {
    it('returns activities within inclusive date range for user', () => {
      const start = new Date('2024-01-01T00:30:00Z')
      const end = new Date('2024-01-01T02:30:00Z')

      const result = dashboard.filterByDateRange('user1', start, end)
      // should include activities at 1h and 2h only
      const ids = result.map(a => a.id)
      expect(ids).toEqual(['2', '3'])
    })

    it('returns empty array when no activities in range', () => {
      const start = new Date('2025-01-01T00:00:00Z')
      const end = new Date('2025-01-02T00:00:00Z')

      const result = dashboard.filterByDateRange('user1', start, end)
      expect(result).toEqual([])
    })

    it('filters by user id as well as date', () => {
      const start = new Date('2024-01-01T00:00:00Z')
      const end = new Date('2024-01-02T23:59:59Z')

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
      // actions: login(1), view(2), purchase(1)
      expect(result.length).toBe(3)

      // sorted by count desc, so 'view' first
      expect(result[0].action).toBe('view')
      expect(result[0].count).toBe(2)
      expect(result[0].percentage).toBe(50) // 2/4 * 100

      const loginGroup = result.find(g => g.action === 'login')
      expect(loginGroup?.count).toBe(1)
      expect(loginGroup?.percentage).toBe(25)

      const purchaseGroup = result.find(g => g.action === 'purchase')
      expect(purchaseGroup?.count).toBe(1)
      expect(purchaseGroup?.percentage).toBe(25)

      // first and last occurrence for 'view'
      const viewActivities = activities.filter(
        a => a.user_id === 'user1' && a.action === 'view'
      )
      const sortedView = [...viewActivities].sort(
        (a, b) => a.timestamp.getTime() - b.timestamp.getTime()
      )
      expect(result[0].firstOccurrence.getTime()).toBe(sortedView[0].timestamp.getTime())
      expect(result[0].lastOccurrence.getTime()).toBe(sortedView[1].timestamp.getTime())
    })

    it('sorts groups by count descending', () => {
      const customActivities: Activity[] = [
        {
          id: 'a1',
          user_id: 'u',
          action: 'a',
          timestamp: new Date('2024-01-01T00:00:00Z')
        },
        {
          id: 'a2',
          user_id: 'u',
          action: 'b',
          timestamp: new Date('2024-01-01T01:00:00Z')
        },
        {
          id: 'a3',
          user_id: 'u',
          action: 'b',
          timestamp: new Date('2024-01-01T02:00:00Z')
        }
      ]
      const d = new ActivityDashboard(customActivities)
      const result = d.aggregateByAction('u')
      expect(result.map(g => g.action)).toEqual(['b', 'a'])
    })
  })

  describe('getTopActions_old', () => {
    it('returns all actions sorted by count when limit not applied', () => {
      const result = dashboard.getTopActions_old('user1')
      expect(result.length).toBe(3)
      expect(result[0].action).toBe('view')
      expect(result[0].count).toBe(2)
    })

    it('calculates percentages based on total actions', () => {
      const result = dashboard.getTopActions_old('user1')
      const view = result.find(r => r.action === 'view')
      const login = result.find(r => r.action === 'login')
      expect(view?.percentage).toBe(50)
      expect(login?.percentage).toBe(25)
    })
  })

  describe('getTopActions', () => {
    it('returns top N actions using aggregateByAction', () => {
      const spy = jest.spyOn(dashboard as any, 'aggregateByAction')
      const result = dashboard.getTopActions('user1', 2)
      expect(spy).toHaveBeenCalledWith('user1')
      expect(result.length).toBe(2)
      expect(result[0].count).toBeGreaterThanOrEqual(result[1].count)
    })

    it('defaults limit to 5 and does not error when fewer actions', () => {
      const result = dashboard.getTopActions('user1')
      // only 3 actions exist, so should return 3
      expect(result.length).toBe(3)
    })
  })

  describe('calculateEngagementScore', () => {
    it('returns 0 when user has no activities', () => {
      const result = dashboard.calculateEngagementScore('unknown')
      expect(result).toBe(0)
    })

    it('calculates engagement score based on summary components', () => {
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

    it('caps each component at its maximum weight', () => {
      const manyActivities: Activity[] = []
      const base = new Date('2024-01-01T00:00:00Z')
      for (let i = 0; i < 200; i++) {
        manyActivities.push({
          id: `m${i}`,
          user_id: 'heavy',
          action: `action${i % 20}`, // 20 different actions
          timestamp: new Date(base.getTime() + i * 60 * 1000)
        })
      }
      const d = new ActivityDashboard(manyActivities)
      const score = d.calculateEngagementScore('heavy')
      // All components should be capped, so max score = 30 + 30 + 40 = 100
      expect(score).toBeLessThanOrEqual(100)
      expect(score).toBe(100)
    })
  })

  describe('period grouping behavior via getActivityTrends', () => {
    it('uses default periodType "day" when not provided', () => {
      const resultExplicit = dashboard.getActivityTrends('user1', 'day')
      const resultDefault = dashboard.getActivityTrends('user1')
      expect(resultDefault).toEqual(resultExplicit)
    })

    it('falls back to day grouping for unknown periodType', () => {
      const anyDashboard: any = dashboard
      const resultWeird = any.getActivityTrends('user1', 'unknown')
      const resultDay = dashboard.getActivityTrends('user1', 'day')
      expect(resultWeird).toEqual(resultDay)
    })
  })
})