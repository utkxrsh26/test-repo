import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'
import { ActivityDashboard, Activity } from '../src/activity-dashboard'

describe('ActivityDashboard', () => {
  let baseDate: Date
  let activities: Activity[]
  let dashboard: ActivityDashboard

  beforeEach(() => {
    baseDate = new Date('2024-01-01T00:00:00.000Z')

    activities = [
      // user1 - multiple days and actions
      {
        id: '1',
        user_id: 'user1',
        action: 'login',
        timestamp: new Date('2024-01-01T10:00:00.000Z'),
      },
      {
        id: '2',
        user_id: 'user1',
        action: 'view',
        timestamp: new Date('2024-01-01T10:10:00.000Z'),
      },
      {
        id: '3',
        user_id: 'user1',
        action: 'view',
        timestamp: new Date('2024-01-02T11:00:00.000Z'),
      },
      {
        id: '4',
        user_id: 'user1',
        action: 'purchase',
        timestamp: new Date('2024-01-03T12:00:00.000Z'),
      },
      {
        id: '5',
        user_id: 'user1',
        action: 'view',
        timestamp: new Date('2024-01-03T12:40:00.000Z'),
      },
      // user2 - single day
      {
        id: '6',
        user_id: 'user2',
        action: 'login',
        timestamp: new Date('2024-01-01T09:00:00.000Z'),
      },
      {
        id: '7',
        user_id: 'user2',
        action: 'view',
        timestamp: new Date('2024-01-01T09:05:00.000Z'),
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

    it('calculates summary metrics correctly for multi-day user', () => {
      const result = dashboard.getUserSummary('user1')
      expect(result).not.toBeNull()
      if (!result) return

      // totalActions: all activities for user1
      expect(result.totalActions).toBe(5)

      // uniqueActions: login, view, purchase
      expect(result.uniqueActions).toBe(3)

      // daysActive: ceil((last-first)/day) with min 1
      // first: 2024-01-01T10:00, last: 2024-01-03T12:40
      const msDiff =
        new Date('2024-01-03T12:40:00.000Z').getTime() -
        new Date('2024-01-01T10:00:00.000Z').getTime()
      const daysActive = Math.max(Math.ceil(msDiff / (1000 * 60 * 60 * 24)), 1)
      const expectedActionsPerDay = parseFloat((5 / daysActive).toFixed(2))
      expect(result.actionsPerDay).toBe(expectedActionsPerDay)

      // mostFrequentAction: 'view' (3 times)
      expect(result.mostFrequentAction).toBe('view')

      // averageActionsPerSession: based on 30-minute gaps
      // user1 timestamps:
      // 10:00, 10:10 (same session)
      // 11:00 (gap 50min >30 => new session)
      // 12:00, 12:40 (same session as 12:00, gap 60min from 11:00 => new session)
      // sessions = 3, actions = 5 => 5/3 = 1.67
      expect(result.averageActionsPerSession).toBe(1.67)
    })

    it('handles single-activity user with daysActive minimum of 1', () => {
      const singleActivity: Activity = {
        id: '8',
        user_id: 'single',
        action: 'login',
        timestamp: baseDate,
      }
      const singleDashboard = new ActivityDashboard([...activities, singleActivity])

      const result = singleDashboard.getUserSummary('single')
      expect(result).not.toBeNull()
      if (!result) return

      expect(result.totalActions).toBe(1)
      expect(result.uniqueActions).toBe(1)
      expect(result.actionsPerDay).toBe(1) // 1 action / 1 day
      expect(result.mostFrequentAction).toBe('login')
      expect(result.averageActionsPerSession).toBe(1)
    })
  })

  describe('getActivityTrends', () => {
    it('returns empty array when user has no activities', () => {
      const result = dashboard.getActivityTrends('unknown')
      expect(result).toEqual([])
    })

    it('groups activities by day and calculates growthRate', () => {
      const result = dashboard.getActivityTrends('user1', 'day')

      // user1 days:
      // 2024-01-01: 2
      // 2024-01-02: 1
      // 2024-01-03: 2
      expect(result).toHaveLength(3)
      expect(result[0]).toEqual({
        period: '2024-01-01',
        count: 2,
        growthRate: 0,
      })
      // growthRate = ((1 - 2) / 2) * 100 = -50
      expect(result[1]).toEqual({
        period: '2024-01-02',
        count: 1,
        growthRate: -50,
      })
      // growthRate = ((2 - 1) / 1) * 100 = 100
      expect(result[2]).toEqual({
        period: '2024-01-03',
        count: 2,
        growthRate: 100,
      })
    })

    it('groups activities by hour when periodType is hour', () => {
      const result = dashboard.getActivityTrends('user1', 'hour')

      // user1 hours:
      // 2024-01-01 10:00: 2
      // 2024-01-02 11:00: 1
      // 2024-01-03 12:00: 2
      expect(result.map(r => r.period)).toEqual([
        '2024-01-01 10:00',
        '2024-01-02 11:00',
        '2024-01-03 12:00',
      ])
      expect(result.map(r => r.count)).toEqual([2, 1, 2])
    })

    it('groups activities by month when periodType is month', () => {
      const result = dashboard.getActivityTrends('user1', 'month')
      // all user1 activities are in 2024-01
      expect(result).toHaveLength(1)
      expect(result[0].period).toBe('2024-01')
      expect(result[0].count).toBe(5)
      expect(result[0].growthRate).toBe(0)
    })

    it('groups activities by week when periodType is week', () => {
      const result = dashboard.getActivityTrends('user1', 'week')
      // All sample dates are in the same ISO-like week per getWeekNumber implementation
      expect(result).toHaveLength(1)
      expect(result[0].count).toBe(5)
      expect(result[0].period.startsWith('2024-W')).toBe(true)
    })
  })

  describe('filterByDateRange', () => {
    it('returns only activities for given user within date range inclusive', () => {
      const start = new Date('2024-01-01T10:05:00.000Z')
      const end = new Date('2024-01-03T12:00:00.000Z')

      const result = dashboard.filterByDateRange('user1', start, end)

      // user1 activities in range:
      // id2: 2024-01-01T10:10
      // id3: 2024-01-02T11:00
      // id4: 2024-01-03T12:00 (inclusive)
      expect(result.map(a => a.id)).toEqual(['2', '3', '4'])
    })

    it('returns empty array when no activities in range', () => {
      const start = new Date('2025-01-01T00:00:00.000Z')
      const end = new Date('2025-01-02T00:00:00.000Z')

      const result = dashboard.filterByDateRange('user1', start, end)
      expect(result).toEqual([])
    })
  })

  describe('aggregateByAction', () => {
    it('returns empty array when user has no activities', () => {
      const result = dashboard.aggregateByAction('unknown')
      expect(result).toEqual([])
    })

    it('aggregates actions with counts, percentages and occurrence dates', () => {
      const result = dashboard.aggregateByAction('user1')

      // user1 actions:
      // login: 1
      // view: 3
      // purchase: 1
      // Sorted by count desc => view, login, purchase (login and purchase same count, order by sort stability)
      const viewGroup = result.find(g => g.action === 'view')
      const loginGroup = result.find(g => g.action === 'login')
      const purchaseGroup = result.find(g => g.action === 'purchase')

      expect(result).toHaveLength(3)

      expect(viewGroup).toBeDefined()
      if (viewGroup) {
        expect(viewGroup.count).toBe(3)
        expect(viewGroup.percentage).toBe(parseFloat(((3 / 5) * 100).toFixed(2)))
        expect(viewGroup.firstOccurrence).toEqual(new Date('2024-01-01T10:10:00.000Z'))
        expect(viewGroup.lastOccurrence).toEqual(new Date('2024-01-03T12:40:00.000Z'))
      }

      expect(loginGroup).toBeDefined()
      if (loginGroup) {
        expect(loginGroup.count).toBe(1)
        expect(loginGroup.percentage).toBe(parseFloat(((1 / 5) * 100).toFixed(2)))
        expect(loginGroup.firstOccurrence).toEqual(new Date('2024-01-01T10:00:00.000Z'))
        expect(loginGroup.lastOccurrence).toEqual(new Date('2024-01-01T10:00:00.000Z'))
      }

      expect(purchaseGroup).toBeDefined()
      if (purchaseGroup) {
        expect(purchaseGroup.count).toBe(1)
        expect(purchaseGroup.percentage).toBe(parseFloat(((1 / 5) * 100).toFixed(2)))
        expect(purchaseGroup.firstOccurrence).toEqual(new Date('2024-01-03T12:00:00.000Z'))
        expect(purchaseGroup.lastOccurrence).toEqual(new Date('2024-01-03T12:00:00.000Z'))
      }

      // Ensure sorted by count descending
      expect(result[0].action).toBe('view')
      expect(result[0].count).toBe(3)
    })
  })

  describe('getTopActions_old', () => {
    it('returns all actions sorted by count without applying limit', () => {
      const result = dashboard.getTopActions_old('user1', 1)

      // Should ignore limit and return all groups
      expect(result).toHaveLength(3)
      expect(result[0].action).toBe('view')
      expect(result[0].count).toBe(3)
    })

    it('calculates percentages and occurrences same as aggregateByAction', () => {
      const result = dashboard.getTopActions_old('user1')
      const viewGroup = result.find(g => g.action === 'view')
      expect(viewGroup).toBeDefined()
      if (!viewGroup) return

      expect(viewGroup.count).toBe(3)
      expect(viewGroup.percentage).toBe(parseFloat(((3 / 5) * 100).toFixed(2)))
      expect(viewGroup.firstOccurrence).toEqual(new Date('2024-01-01T10:10:00.000Z'))
      expect(viewGroup.lastOccurrence).toEqual(new Date('2024-01-03T12:40:00.000Z'))
    })
  })

  describe('getTopActions', () => {
    it('returns top N actions based on aggregateByAction', () => {
      const spy = jest.spyOn(dashboard as any, 'aggregateByAction')
      const result = dashboard.getTopActions('user1', 2)

      expect(spy).toHaveBeenCalledWith('user1')
      expect(result).toHaveLength(2)
      expect(result[0].action).toBe('view')
      expect(result[1].count).toBe(1)
    })

    it('defaults limit to 5 when not provided', () => {
      const result = dashboard.getTopActions('user1')
      // Only 3 actions exist, so should return 3
      expect(result).toHaveLength(3)
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

    it('calculates score based on volume, diversity and frequency caps', () => {
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

    it('respects upper caps for each component', () => {
      const manyActivities: Activity[] = []
      for (let i = 0; i < 200; i++) {
        manyActivities.push({
          id: `m-${i}`,
          user_id: 'heavy',
          action: `action-${i % 20}`, // 20 unique actions
          timestamp: new Date(baseDate.getTime() + i * 60 * 60 * 1000), // hourly
        })
      }
      const heavyDashboard = new ActivityDashboard(manyActivities)
      const score = heavyDashboard.calculateEngagementScore('heavy')

      // All components should be capped at their max:
      // volumeScore: 30, diversityScore: 30, frequencyScore: 40 => total 100
      expect(score).toBe(100)
    })
  })

  describe('session calculation via getUserSummary (calculateAverageActionsPerSession)', () => {
    it('returns 0 averageActionsPerSession when user has no activities', () => {
      const emptyDashboard = new ActivityDashboard([])
      const summary = emptyDashboard.getUserSummary('user1')
      expect(summary).toBeNull()
    })

    it('creates new session when gap exceeds 30 minutes', () => {
      const sessionActivities: Activity[] = [
        {
          id: 's1',
          user_id: 'sess',
          action: 'a',
          timestamp: new Date('2024-01-01T10:00:00.000Z'),
        },
        {
          id: 's2',
          user_id: 'sess',
          action: 'b',
          timestamp: new Date('2024-01-01T10:20:00.000Z'), // same session
        },
        {
          id: 's3',
          user_id: 'sess',
          action: 'c',
          timestamp: new Date('2024-01-01T11:00:01.000Z'), // >30 min gap => new session
        },
      ]
      const sessDashboard = new ActivityDashboard(sessionActivities)
      const summary = sessDashboard.getUserSummary('sess')
      expect(summary).not.toBeNull()
      if (!summary) return

      // 3 actions, 2 sessions => 1.5
      expect(summary.averageActionsPerSession).toBe(1.5)
    })
  })
})