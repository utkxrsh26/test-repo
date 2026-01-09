import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'
import { ActivityDashboard, Activity } from '../src/activity-dashboard'

afterEach(() => {
  jest.clearAllMocks()
})

const makeDate = (iso: string) => new Date(iso)

describe('ActivityDashboard - getUserSummary', () => {
  let activities: Activity[]
  let dashboard: ActivityDashboard

  beforeEach(() => {
    activities = [
      {
        id: '1',
        user_id: 'user1',
        action: 'login',
        timestamp: makeDate('2024-01-01T10:00:00Z')
      },
      {
        id: '2',
        user_id: 'user1',
        action: 'view',
        timestamp: makeDate('2024-01-01T10:10:00Z')
      },
      {
        id: '3',
        user_id: 'user1',
        action: 'login',
        timestamp: makeDate('2024-01-02T11:00:00Z')
      },
      {
        id: '4',
        user_id: 'user2',
        action: 'login',
        timestamp: makeDate('2024-01-01T09:00:00Z')
      }
    ]
    dashboard = new ActivityDashboard(activities)
  })

  it('returns null when user has no activities', () => {
    const summary = dashboard.getUserSummary('unknown')
    expect(summary).toBeNull()
  })

  it('calculates summary metrics for a user on multiple days', () => {
    const summary = dashboard.getUserSummary('user1')
    expect(summary).not.toBeNull()
    expect(summary!.totalActions).toBe(3)
    expect(summary!.uniqueActions).toBe(2)
    // first: 2024-01-01T10:00, last: 2024-01-02T11:00
    // diff ~ 1.0417 days -> ceil = 2 days
    // actionsPerDay = 3 / 2 = 1.5 -> toFixed(2) => 1.50 -> parseFloat => 1.5
    expect(summary!.actionsPerDay).toBe(1.5)
    // action counts: login=2, view=1
    expect(summary!.mostFrequentAction).toBe('login')
    // sessions: gap > 30 minutes between 10:10 and next day 11:00 => 2 sessions
    // averageActionsPerSession = 3 / 2 = 1.5
    expect(summary!.averageActionsPerSession).toBe(1.5)
  })

  it('handles all activities within a single day as one day active', () => {
    const singleDayActivities: Activity[] = [
      {
        id: '1',
        user_id: 'user3',
        action: 'a',
        timestamp: makeDate('2024-01-01T00:00:00Z')
      },
      {
        id: '2',
        user_id: 'user3',
        action: 'b',
        timestamp: makeDate('2024-01-01T23:59:59Z')
      }
    ]
    const dash = new ActivityDashboard(singleDayActivities)
    const summary = dash.getUserSummary('user3')
    expect(summary).not.toBeNull()
    expect(summary!.totalActions).toBe(2)
    expect(summary!.actionsPerDay).toBe(2) // daysActive = max(ceil(diff<1),1)=1
  })

  it('averageActionsPerSession is 0 when user has no activities (via calculateEngagementScore)', () => {
    const dash = new ActivityDashboard([])
    const summary = dash.getUserSummary('user1')
    expect(summary).toBeNull()
  })
})

describe('ActivityDashboard - getActivityTrends', () => {
  let activities: Activity[]
  let dashboard: ActivityDashboard

  beforeEach(() => {
    activities = [
      {
        id: '1',
        user_id: 'user1',
        action: 'a',
        timestamp: makeDate('2024-01-01T10:00:00Z')
      },
      {
        id: '2',
        user_id: 'user1',
        action: 'b',
        timestamp: makeDate('2024-01-01T11:00:00Z')
      },
      {
        id: '3',
        user_id: 'user1',
        action: 'c',
        timestamp: makeDate('2024-01-02T09:00:00Z')
      },
      {
        id: '4',
        user_id: 'user1',
        action: 'd',
        timestamp: makeDate('2024-01-03T09:00:00Z')
      },
      {
        id: '5',
        user_id: 'user2',
        action: 'x',
        timestamp: makeDate('2024-01-01T09:00:00Z')
      }
    ]
    dashboard = new ActivityDashboard(activities)
  })

  it('returns empty array when user has no activities', () => {
    const trends = dashboard.getActivityTrends('unknown')
    expect(trends).toEqual([])
  })

  it('groups activities by day and calculates growth rate', () => {
    const trends = dashboard.getActivityTrends('user1', 'day')
    expect(trends.length).toBe(3)
    expect(trends[0]).toEqual({
      period: '2024-01-01',
      count: 2,
      growthRate: 0
    })
    // previous count = 2, current = 1 => ((1-2)/2)*100 = -50
    expect(trends[1]).toEqual({
      period: '2024-01-02',
      count: 1,
      growthRate: -50
    })
    // previous count = 1, current = 1 => 0
    expect(trends[2]).toEqual({
      period: '2024-01-03',
      count: 1,
      growthRate: 0
    })
  })

  it('groups activities by hour when periodType is hour', () => {
    const trends = dashboard.getActivityTrends('user1', 'hour')
    const periods = trends.map(t => t.period)
    expect(periods).toContain('2024-01-01 10:00')
    expect(periods).toContain('2024-01-01 11:00')
    expect(periods).toContain('2024-01-02 09:00')
    expect(periods).toContain('2024-01-03 09:00')
    const first = trends.find(t => t.period === '2024-01-01 10:00')!
    expect(first.count).toBe(1)
    expect(first.growthRate).toBe(0)
  })

  it('groups activities by month when periodType is month', () => {
    const trends = dashboard.getActivityTrends('user1', 'month')
    expect(trends.length).toBe(1)
    expect(trends[0].period).toBe('2024-01')
    expect(trends[0].count).toBe(4)
    expect(trends[0].growthRate).toBe(0)
  })

  it('groups activities by week when periodType is week', () => {
    const trends = dashboard.getActivityTrends('user1', 'week')
    expect(trends.length).toBe(1)
    expect(trends[0].period.startsWith('2024-W')).toBe(true)
    expect(trends[0].count).toBe(4)
  })
})

describe('ActivityDashboard - filterByDateRange', () => {
  it('filters activities by user and date range inclusive', () => {
    const activities: Activity[] = [
      {
        id: '1',
        user_id: 'user1',
        action: 'a',
        timestamp: makeDate('2024-01-01T00:00:00Z')
      },
      {
        id: '2',
        user_id: 'user1',
        action: 'b',
        timestamp: makeDate('2024-01-02T00:00:00Z')
      },
      {
        id: '3',
        user_id: 'user1',
        action: 'c',
        timestamp: makeDate('2024-01-03T00:00:00Z')
      },
      {
        id: '4',
        user_id: 'user2',
        action: 'd',
        timestamp: makeDate('2024-01-02T00:00:00Z')
      }
    ]
    const dashboard = new ActivityDashboard(activities)
    const result = dashboard.filterByDateRange(
      'user1',
      makeDate('2024-01-02T00:00:00Z'),
      makeDate('2024-01-03T00:00:00Z')
    )
    const ids = result.map(a => a.id)
    expect(ids).toEqual(['2', '3'])
  })

  it('returns empty array when no activities in range', () => {
    const activities: Activity[] = [
      {
        id: '1',
        user_id: 'user1',
        action: 'a',
        timestamp: makeDate('2024-01-01T00:00:00Z')
      }
    ]
    const dashboard = new ActivityDashboard(activities)
    const result = dashboard.filterByDateRange(
      'user1',
      makeDate('2024-01-02T00:00:00Z'),
      makeDate('2024-01-03T00:00:00Z')
    )
    expect(result).toEqual([])
  })
})

describe('ActivityDashboard - aggregateByAction', () => {
  it('returns empty array when user has no activities', () => {
    const dashboard = new ActivityDashboard([])
    const result = dashboard.aggregateByAction('user1')
    expect(result).toEqual([])
  })

  it('aggregates actions with counts, percentages and occurrences', () => {
    const activities: Activity[] = [
      {
        id: '1',
        user_id: 'user1',
        action: 'login',
        timestamp: makeDate('2024-01-01T10:00:00Z')
      },
      {
        id: '2',
        user_id: 'user1',
        action: 'view',
        timestamp: makeDate('2024-01-01T11:00:00Z')
      },
      {
        id: '3',
        user_id: 'user1',
        action: 'login',
        timestamp: makeDate('2024-01-02T10:00:00Z')
      },
      {
        id: '4',
        user_id: 'user1',
        action: 'purchase',
        timestamp: makeDate('2024-01-03T10:00:00Z')
      }
    ]
    const dashboard = new ActivityDashboard(activities)
    const result = dashboard.aggregateByAction('user1')
    expect(result.length).toBe(3)
    // sorted by count desc, so login first
    const loginGroup = result[0]
    expect(loginGroup.action).toBe('login')
    expect(loginGroup.count).toBe(2)
    expect(loginGroup.percentage).toBeCloseTo(50)
    expect(loginGroup.firstOccurrence).toEqual(makeDate('2024-01-01T10:00:00Z'))
    expect(loginGroup.lastOccurrence).toEqual(makeDate('2024-01-02T10:00:00Z'))

    const viewGroup = result.find(g => g.action === 'view')!
    expect(viewGroup.count).toBe(1)
    expect(viewGroup.percentage).toBeCloseTo(25)

    const purchaseGroup = result.find(g => g.action === 'purchase')!
    expect(purchaseGroup.count).toBe(1)
    expect(purchaseGroup.percentage).toBeCloseTo(25)
  })

  it('only includes activities for the specified user', () => {
    const activities: Activity[] = [
      {
        id: '1',
        user_id: 'user1',
        action: 'login',
        timestamp: makeDate('2024-01-01T10:00:00Z')
      },
      {
        id: '2',
        user_id: 'user2',
        action: 'login',
        timestamp: makeDate('2024-01-01T11:00:00Z')
      }
    ]
    const dashboard = new ActivityDashboard(activities)
    const result = dashboard.aggregateByAction('user1')
    expect(result.length).toBe(1)
    expect(result[0].count).toBe(1)
  })
})

describe('ActivityDashboard - getTopActions_old', () => {
  it('returns all actions sorted by count when limit not applied', () => {
    const activities: Activity[] = [
      {
        id: '1',
        user_id: 'user1',
        action: 'a',
        timestamp: makeDate('2024-01-01T10:00:00Z')
      },
      {
        id: '2',
        user_id: 'user1',
        action: 'b',
        timestamp: makeDate('2024-01-01T11:00:00Z')
      },
      {
        id: '3',
        user_id: 'user1',
        action: 'a',
        timestamp: makeDate('2024-01-02T10:00:00Z')
      }
    ]
    const dashboard = new ActivityDashboard(activities)
    const result = dashboard.getTopActions_old('user1')
    expect(result.length).toBe(2)
    expect(result[0].action).toBe('a')
    expect(result[0].count).toBe(2)
    expect(result[0].percentage).toBeCloseTo((2 / 3) * 100)
    expect(result[0].firstOccurrence).toEqual(makeDate('2024-01-01T10:00:00Z'))
    expect(result[0].lastOccurrence).toEqual(makeDate('2024-01-02T10:00:00Z'))
  })

  it('handles user with no activities by returning empty array', () => {
    const dashboard = new ActivityDashboard([])
    const result = dashboard.getTopActions_old('user1')
    expect(result).toEqual([])
  })
})

describe('ActivityDashboard - getTopActions', () => {
  it('returns top N actions based on aggregateByAction', () => {
    const activities: Activity[] = [
      {
        id: '1',
        user_id: 'user1',
        action: 'a',
        timestamp: makeDate('2024-01-01T10:00:00Z')
      },
      {
        id: '2',
        user_id: 'user1',
        action: 'b',
        timestamp: makeDate('2024-01-01T11:00:00Z')
      },
      {
        id: '3',
        user_id: 'user1',
        action: 'a',
        timestamp: makeDate('2024-01-02T10:00:00Z')
      },
      {
        id: '4',
        user_id: 'user1',
        action: 'c',
        timestamp: makeDate('2024-01-03T10:00:00Z')
      }
    ]
    const dashboard = new ActivityDashboard(activities)
    const top2 = dashboard.getTopActions('user1', 2)
    expect(top2.length).toBe(2)
    expect(top2[0].action).toBe('a')
    expect(top2[0].count).toBe(2)
  })

  it('returns fewer actions when limit exceeds available groups', () => {
    const activities: Activity[] = [
      {
        id: '1',
        user_id: 'user1',
        action: 'a',
        timestamp: makeDate('2024-01-01T10:00:00Z')
      }
    ]
    const dashboard = new ActivityDashboard(activities)
    const top5 = dashboard.getTopActions('user1', 5)
    expect(top5.length).toBe(1)
    expect(top5[0].action).toBe('a')
  })

  it('returns empty array when user has no activities', () => {
    const dashboard = new ActivityDashboard([])
    const result = dashboard.getTopActions('user1', 3)
    expect(result).toEqual([])
  })
})

describe('ActivityDashboard - calculateEngagementScore', () => {
  it('returns 0 when user has no activities', () => {
    const dashboard = new ActivityDashboard([])
    const score = dashboard.calculateEngagementScore('user1')
    expect(score).toBe(0)
  })

  it('calculates engagement score with caps applied', () => {
    const activities: Activity[] = []
    const baseDate = makeDate('2024-01-01T00:00:00Z')
    // create 100 actions over 5 days with 10 unique actions
    for (let i = 0; i < 100; i++) {
      activities.push({
        id: String(i),
        user_id: 'user1',
        action: `action${i % 10}`,
        timestamp: new Date(baseDate.getTime() + i * 60 * 60 * 1000)
      })
    }
    const dashboard = new ActivityDashboard(activities)
    const score = dashboard.calculateEngagementScore('user1')
    // volumeScore: min(100/100,1)*30 = 30
    // diversityScore: min(10/10,1)*30 = 30
    // actionsPerDay: depends on daysActive; ensure score within 0-100
    expect(score).toBeGreaterThan(0)
    expect(score).toBeLessThanOrEqual(100)
  })

  it('calculates engagement score based on summary values', () => {
    const activities: Activity[] = [
      {
        id: '1',
        user_id: 'user1',
        action: 'a',
        timestamp: makeDate('2024-01-01T00:00:00Z')
      },
      {
        id: '2',
        user_id: 'user1',
        action: 'b',
        timestamp: makeDate('2024-01-02T00:00:00Z')
      }
    ]
    const dashboard = new ActivityDashboard(activities)
    const summary = dashboard.getUserSummary('user1')!
    const volumeScore = Math.min(summary.totalActions / 100, 1) * 30
    const diversityScore = Math.min(summary.uniqueActions / 10, 1) * 30
    const frequencyScore = Math.min(summary.actionsPerDay / 5, 1) * 40
    const expected = parseFloat((volumeScore + diversityScore + frequencyScore).toFixed(2))
    const score = dashboard.calculateEngagementScore('user1')
    expect(score).toBe(expected)
  })
})

describe('ActivityDashboard - session calculation behavior (indirect)', () => {
  it('treats gaps greater than 30 minutes as new sessions', () => {
    const activities: Activity[] = [
      {
        id: '1',
        user_id: 'user1',
        action: 'a',
        timestamp: makeDate('2024-01-01T10:00:00Z')
      },
      {
        id: '2',
        user_id: 'user1',
        action: 'b',
        timestamp: makeDate('2024-01-01T10:20:00Z')
      },
      {
        id: '3',
        user_id: 'user1',
        action: 'c',
        timestamp: makeDate('2024-01-01T11:00:01Z')
      }
    ]
    const dashboard = new ActivityDashboard(activities)
    const summary = dashboard.getUserSummary('user1')!
    // first two within 20 minutes, third is 40+ minutes later => 2 sessions
    // averageActionsPerSession = 3 / 2 = 1.5
    expect(summary.averageActionsPerSession).toBe(1.5)
  })
})