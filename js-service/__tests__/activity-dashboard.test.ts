import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'
import { ActivityDashboard, Activity } from '../src/activity-dashboard'

describe('ActivityDashboard', () => {
  let baseDate: Date
  let activities: Activity[]
  let dashboard: ActivityDashboard

  beforeEach(() => {
    baseDate = new Date('2024-01-01T00:00:00.000Z')

    activities = [
      // user1 actions on same day within one session
      {
        id: '1',
        user_id: 'user1',
        action: 'login',
        timestamp: new Date(baseDate.getTime() + 1 * 60 * 1000) // +1 min
      },
      {
        id: '2',
        user_id: 'user1',
        action: 'view',
        timestamp: new Date(baseDate.getTime() + 5 * 60 * 1000) // +5 min
      },
      {
        id: '3',
        user_id: 'user1',
        action: 'view',
        timestamp: new Date(baseDate.getTime() + 10 * 60 * 1000) // +10 min
      },
      // user1 actions next day, new session (gap > 30 min)
      {
        id: '4',
        user_id: 'user1',
        action: 'purchase',
        timestamp: new Date(baseDate.getTime() + 24 * 60 * 60 * 1000 + 60 * 60 * 1000) // +25h
      },
      // user2 actions
      {
        id: '5',
        user_id: 'user2',
        action: 'login',
        timestamp: new Date(baseDate.getTime() + 2 * 60 * 60 * 1000) // +2h
      },
      {
        id: '6',
        user_id: 'user2',
        action: 'logout',
        timestamp: new Date(baseDate.getTime() + 3 * 60 * 60 * 1000) // +3h
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

      // daysActive: from first to last activity for user1
      const user1Acts = activities.filter(a => a.user_id === 'user1')
      const sorted = [...user1Acts].sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
      const first = sorted[0].timestamp
      const last = sorted[sorted.length - 1].timestamp
      const diffMs = last.getTime() - first.getTime()
      const daysActive = Math.max(Math.ceil(diffMs / (1000 * 60 * 60 * 24)), 1)
      const expectedActionsPerDay = parseFloat((user1Acts.length / daysActive).toFixed(2))
      expect(result.actionsPerDay).toBe(expectedActionsPerDay)

      // mostFrequentAction: 'view' appears twice
      expect(result.mostFrequentAction).toBe('view')

      // averageActionsPerSession: 3 actions in first session, 1 in second => 4/2 = 2.00
      expect(result.averageActionsPerSession).toBe(2.0)
    })

    it('handles single activity correctly (daysActive minimum 1)', () => {
      const singleActivity: Activity = {
        id: '7',
        user_id: 'single',
        action: 'only',
        timestamp: new Date(baseDate.getTime() + 1000)
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

    it('groups activities by day and calculates growthRate', () => {
      const result = dashboard.getActivityTrends('user1', 'day')
      // user1 has activities on 2 different days
      expect(result.length).toBe(2)

      const periods = result.map(r => r.period)
      expect(periods[0] <= periods[1]).toBe(true)

      const firstDay = result[0]
      const secondDay = result[1]

      // first period growthRate should be 0
      expect(firstDay.growthRate).toBe(0)

      // counts should match number of activities per day
      const groupedByDay: Record<string, number> = {}
      activities
        .filter(a => a.user_id === 'user1')
        .forEach(a => {
          const d = a.timestamp
          const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
            d.getDate()
          ).padStart(2, '0')}`
          groupedByDay[key] = (groupedByDay[key] || 0) + 1
        })

      expect(firstDay.count).toBe(groupedByDay[firstDay.period])
      expect(secondDay.count).toBe(groupedByDay[secondDay.period])

      // growthRate for second period: ((count2 - count1) / count1) * 100
      const expectedGrowth =
        groupedByDay[firstDay.period] > 0
          ? parseFloat(
              (((groupedByDay[secondDay.period] - groupedByDay[firstDay.period]) /
                groupedByDay[firstDay.period]) *
                100).toFixed(2)
            )
          : 0
      expect(secondDay.growthRate).toBe(expectedGrowth)
    })

    it('groups activities by hour when periodType is hour', () => {
      const result = dashboard.getActivityTrends('user2', 'hour')
      // user2 has 2 activities in different hours
      expect(result.length).toBe(2)
      result.forEach(r => {
        expect(typeof r.period).toBe('string')
        expect(r.period.includes(':00')).toBe(true)
      })
    })

    it('groups activities by week and month', () => {
      const weekTrends = dashboard.getActivityTrends('user1', 'week')
      const monthTrends = dashboard.getActivityTrends('user1', 'month')

      expect(weekTrends.length).toBeGreaterThanOrEqual(1)
      expect(monthTrends.length).toBe(1)

      weekTrends.forEach(t => {
        expect(t.period).toMatch(/W\d{2}$/)
      })
      monthTrends.forEach(t => {
        expect(t.period).toMatch(/^\d{4}-\d{2}$/)
      })
    })
  })

  describe('filterByDateRange', () => {
    it('returns only activities for given user within date range', () => {
      const start = new Date(baseDate.getTime() + 30 * 60 * 1000) // +30 min
      const end = new Date(baseDate.getTime() + 26 * 60 * 60 * 1000) // +26h

      const result = dashboard.filterByDateRange('user1', start, end)

      // Should include id 3 and 4 for user1
      const ids = result.map(a => a.id).sort()
      expect(ids).toEqual(['3', '4'])
    })

    it('returns empty array when no activities in range', () => {
      const start = new Date(baseDate.getTime() - 10 * 24 * 60 * 60 * 1000)
      const end = new Date(baseDate.getTime() - 5 * 24 * 60 * 60 * 1000)

      const result = dashboard.filterByDateRange('user1', start, end)
      expect(result).toEqual([])
    })
  })

  describe('aggregateByAction', () => {
    it('returns empty array when user has no activities', () => {
      const result = dashboard.aggregateByAction('unknown')
      expect(result).toEqual([])
    })

    it('aggregates actions with counts, percentages and occurrences', () => {
      const result = dashboard.aggregateByAction('user1')

      // user1 actions: login(1), view(2), purchase(1)
      expect(result.length).toBe(3)

      // sorted by count descending, so 'view' first
      expect(result[0].action).toBe('view')
      expect(result[0].count).toBe(2)

      const total = 4
      const viewGroup = result.find(g => g.action === 'view')
      const loginGroup = result.find(g => g.action === 'login')
      const purchaseGroup = result.find(g => g.action === 'purchase')

      expect(viewGroup).toBeDefined()
      expect(loginGroup).toBeDefined()
      expect(purchaseGroup).toBeDefined()

      if (!viewGroup || !loginGroup || !purchaseGroup) return

      expect(viewGroup.percentage).toBe(parseFloat(((2 / total) * 100).toFixed(2)))
      expect(loginGroup.percentage).toBe(parseFloat(((1 / total) * 100).toFixed(2)))
      expect(purchaseGroup.percentage).toBe(parseFloat(((1 / total) * 100).toFixed(2)))

      // first/last occurrence should match timestamps for that action
      const viewActs = activities.filter(a => a.user_id === 'user1' && a.action === 'view')
      const sortedView = [...viewActs].sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
      expect(viewGroup.firstOccurrence.getTime()).toBe(sortedView[0].timestamp.getTime())
      expect(viewGroup.lastOccurrence.getTime()).toBe(sortedView[sortedView.length - 1].timestamp.getTime())
    })

    it('does not double-count actions when iterating', () => {
      const result = dashboard.aggregateByAction('user2')
      // user2 has 2 different actions
      expect(result.length).toBe(2)
      const actions = result.map(r => r.action).sort()
      expect(actions).toEqual(['login', 'logout'])
    })
  })

  describe('getTopActions_old', () => {
    it('returns all actions sorted by count descending, ignoring limit parameter', () => {
      const result = dashboard.getTopActions_old('user1', 1)
      // Implementation does not slice by limit, so should return 3 groups
      expect(result.length).toBe(3)
      expect(result[0].action).toBe('view')
      expect(result[0].count).toBe(2)
    })

    it('calculates percentages based on total user actions', () => {
      const result = dashboard.getTopActions_old('user2')
      const total = 2
      result.forEach(group => {
        expect(group.percentage).toBe(parseFloat(((group.count / total) * 100).toFixed(2)))
      })
    })
  })

  describe('getTopActions', () => {
    it('returns top N actions based on aggregateByAction', () => {
      const spy = jest.spyOn(dashboard, 'aggregateByAction' as any)
      const result = dashboard.getTopActions('user1', 2)

      expect(spy).toHaveBeenCalledWith('user1')
      expect(result.length).toBe(2)
      // Should be the two most frequent actions: view(2) and login(1) or purchase(1)
      expect(result[0].action).toBe('view')
      expect(result[0].count).toBe(2)
    })

    it('returns all actions when limit exceeds available groups', () => {
      const result = dashboard.getTopActions('user2', 10)
      expect(result.length).toBe(2)
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
          action: `action${i % 20}`, // 20 unique actions
          timestamp: new Date(baseDate.getTime() + i * 60 * 1000)
        })
      }
      const heavyDashboard = new ActivityDashboard(manyActivities)
      const score = heavyDashboard.calculateEngagementScore('heavy')

      // All components should be capped: volume 30, diversity 30, frequency 40 => 100
      expect(score).toBe(100)
    })
  })

  describe('private behavior via public methods', () => {
    it('calculateAverageActionsPerSession groups sessions by 30-minute gaps', () => {
      const userId = 'sessionUser'
      const sessionActivities: Activity[] = [
        {
          id: 's1',
          user_id: userId,
          action: 'a',
          timestamp: new Date(baseDate.getTime())
        },
        {
          id: 's2',
          user_id: userId,
          action: 'b',
          timestamp: new Date(baseDate.getTime() + 10 * 60 * 1000) // +10 min same session
        },
        {
          id: 's3',
          user_id: userId,
          action: 'c',
          timestamp: new Date(baseDate.getTime() + 31 * 60 * 1000) // +31 min new session
        }
      ]
      const d = new ActivityDashboard(sessionActivities)
      const summary = d.getUserSummary(userId)
      expect(summary).not.toBeNull()
      if (!summary) return

      // 3 actions, 2 sessions => 1.5
      expect(summary.averageActionsPerSession).toBe(1.5)
    })

    it('groupByPeriod default behavior matches day grouping', () => {
      const trendsDefault = dashboard.getActivityTrends('user1')
      const trendsDay = dashboard.getActivityTrends('user1', 'day')

      expect(trendsDefault).toEqual(trendsDay)
    })
  })
})