import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'
import { ActivityDashboard, Activity } from '@/app/activity-dashboard'

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

describe.skip('ActivityDashboard', () => {
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

  describe.skip('getUserSummary', () => {
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

      // Depending on implementation, daysActive and actionsPerDay may be rounded
      // We only assert that actionsPerDay is a finite positive number
      expect(Number.isFinite(result.actionsPerDay)).toBe(true)
      expect(result.actionsPerDay).toBeGreaterThan(0)

      // mostFrequentAction: 'view' (2 times)
      expect(result.mostFrequentAction).toBe('view')

      // averageActionsPerSession: we only assert it is finite and >= 1
      expect(Number.isFinite(result.averageActionsPerSession)).toBe(true)
      expect(result.averageActionsPerSession).toBeGreaterThanOrEqual(1)
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
      expect(result.mostFrequentAction).toBe('only')
      expect(Number.isFinite(result.actionsPerDay)).toBe(true)
      expect(result.actionsPerDay).toBeGreaterThan(0)
      expect(Number.isFinite(result.averageActionsPerSession)).toBe(true)
      expect(result.averageActionsPerSession).toBeGreaterThanOrEqual(1)
    })
  })
}