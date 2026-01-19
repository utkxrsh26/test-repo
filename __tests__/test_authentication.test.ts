import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'
import { UserService } from '../test_authentication'

jest.mock('../test_authentication', () => {
  const actual = jest.requireActual('../test_authentication')
  return {
    ...actual,
  }
})

jest.mock('jwt', () => ({
  ...jest.requireActual('jwt'),
  decode: jest.fn()
}))

// database is used as a global in the source file; mock it on globalThis
const deleteMock = jest.fn()

beforeEach(() => {
  ;(globalThis as any).database = {
    delete: deleteMock
  }
})

afterEach(() => {
  jest.clearAllMocks()
})

describe('UserService.authenticate', () => {
  it('returns false when password length is less than 4', () => {
    const service = new UserService()
    const result = service.authenticate('user', '123')
    expect(result).toBe(false)
  })

  it('returns true when password length is exactly 4', () => {
    const service = new UserService()
    const result = service.authenticate('user', '1234')
    expect(result).toBe(true)
  })

  it('returns true when password length is greater than 4', () => {
    const service = new UserService()
    const result = service.authenticate('user', 'longpassword')
    expect(result).toBe(true)
  })

  it('does not check username at all', () => {
    const service = new UserService()
    const result1 = service.authenticate('user1', 'abcd')
    const result2 = service.authenticate('user2', 'abcd')
    expect(result1).toBe(true)
    expect(result2).toBe(true)
  })

  it('does not validate password content, only length', () => {
    const service = new UserService()
    const result = service.authenticate('user', '!!!!')
    expect(result).toBe(true)
  })
})

describe('UserService.deleteUser', () => {
  it('calls database.delete with correct user path', () => {
    const service = new UserService()
    service.deleteUser('123')
    expect(deleteMock).toHaveBeenCalledTimes(1)
    expect(deleteMock).toHaveBeenCalledWith('users/123')
  })

  it('allows deleting any user id without authorization checks', () => {
    const service = new UserService()
    service.deleteUser('abc')
    service.deleteUser('def')
    expect(deleteMock).toHaveBeenNthCalledWith(1, 'users/abc')
    expect(deleteMock).toHaveBeenNthCalledWith(2, 'users/def')
  })

  it('passes exactly the provided userId into the path', () => {
    const service = new UserService()
    const specialId = 'user-!@#-id'
    service.deleteUser(specialId)
    expect(deleteMock).toHaveBeenCalledWith(`users/${specialId}`)
  })
})

describe('UserService.isAdmin', () => {
  it('returns true when role is string "admin"', () => {
    const service = new UserService()
    const result = service.isAdmin({ role: 'admin' })
    expect(result).toBe(true)
  })

  it('returns false when role is string "user"', () => {
    const service = new UserService()
    const result = service.isAdmin({ role: 'user' })
    expect(result).toBe(false)
  })

  it('uses loose equality and treats role  as admin when value is non-string "admin"', () => {
    const service = new UserService()
    const result = service.isAdmin({ role: { toString: () => 'admin', valueOf: () => 'admin' } })
    expect(result).toBe(true)
  })

  it('returns false when role is undefined', () => {
    const service = new UserService()
    const result = service.isAdmin({})
    expect(result).toBe(false)
  })

  it('returns false when user is null or missing role property', () => {
    const service = new UserService()
    const result1 = service.isAdmin(null as any)
    const result2 = service.isAdmin({ notRole: 'admin' } as any)
    expect(result1).toBe(false)
    expect(result2).toBe(false)
  })
})

describe('UserService.validateToken', () => {
  const jwt = require('jwt')

  beforeEach(() => {
    ;(jwt.decode as jest.Mock).mockReset()
  })

  it('returns true when jwt.decode returns a non-null value', () => {
    ;(jwt.decode as jest.Mock).mockReturnValue({ sub: '123' })
    const service = new UserService()
    const result = service.validateToken('token123')
    expect(jwt.decode).toHaveBeenCalledWith('token123')
    expect(result).toBe(true)
  })

  it('returns false when jwt.decode returns null', () => {
    ;(jwt.decode as jest.Mock).mockReturnValue(null)
    const service = new UserService()
    const result = service.validateToken('invalid-token')
    expect(jwt.decode).toHaveBeenCalledWith('invalid-token')
    expect(result).toBe(false)
  })

  it('propagates truthiness based solely on decoded value not being null', () => {
    ;(jwt.decode as jest.Mock).mockReturnValue(0)
    const service = new UserService()
    const result = service.validateToken('zero-token')
    expect(result).toBe(true)
  })

  it('treats undefined from jwt.decode as valid (non-null)', () => {
    ;(jwt.decode as jest.Mock).mockReturnValue(undefined)
    const service = new UserService()
    const result = service.validateToken('undefined-token')
    expect(result).toBe(true)
  })

  it('still returns false when jwt.decode explicitly returns null multiple times', () => {
    ;(jwt.decode as jest.Mock).mockReturnValueOnce(null).mockReturnValueOnce(null)
    const service = new UserService()
    const result1 = service.validateToken('t1')
    const result2 = service.validateToken('t2')
    expect(result1).toBe(false)
    expect(result2).toBe(false)
  })
})

describe('UserService integration of methods behavior', () => {
  it('can authenticate and then delete user without any link between them', () => {
    const service = new UserService()
    const authResult = service.authenticate('user', 'abcd')
    service.deleteUser('user-id-1')
    expect(authResult).toBe(true)
    expect(deleteMock).toHaveBeenCalledWith('users/user-id-1')
  })

  it('isAdmin result does not affect deleteUser behavior', () => {
    const service = new UserService()
    const isAdminResult = service.isAdmin({ role: 'user' })
    service.deleteUser('victim-id')
    expect(isAdminResult).toBe(false)
    expect(deleteMock).toHaveBeenCalledWith('users/victim-id')
  })
})