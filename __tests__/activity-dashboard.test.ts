import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'
import { ActivityDashboard, Activity } from '../src/activity-dashboard'

// Mock external libs defensively in case implementation uses them
jest.mock('date-fns', () => ({
  ...jest.requireActual('date-fns'),
  format: jest.fn((date, fmt) => '2024-01-01'),
  subMonths: jest.fn((date, n) => new Date('2024-01-01'))
}))

jest.mock('react-use', () => ({
  ...jest.requireActual('react-use'),
  useMedia: jest.fn()
}))

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

  describe('trends and helpers', () => {
    it('finds most frequent action for non-empty list', () => {
      const result = dashboard.getUserSummary('user1')
      expect(result).not.toBeNull()
      if (!result) return
      expect(result.mostFrequentAction).toBe('view')
    })

    it('handles empty activities when computing most frequent action', () => {
      const emptyDashboard = new ActivityDashboard([])
      const summary = emptyDashboard.getUserSummary('any')
      expect(summary).toBeNull()
    })

    it('supports multiple users independently', () => {
      const user1 = dashboard.getUserSummary('user1')
      const user2 = dashboard.getUserSummary('user2')

      expect(user1).not.toBeNull()
      expect(user2).not.toBeNull()
      if (!user1 || !user2) return

      expect(user1.totalActions).toBe(4)
      expect(user2.totalActions).toBe(1)
    })
  })
})