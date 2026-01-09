import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'
import { UserService } from '../test_authentication'

jest.mock('../test_authentication', () => ({
  ...jest.requireActual('../test_authentication')
}))

// Mock global dependencies used inside UserService methods
const database = {
  delete: jest.fn()
}

const jwt = {
  decode: jest.fn()
}

// @ts-ignore - attach mocks to global scope so the class can use them
;(global as any).database = database
// @ts-ignore
;(global as any).jwt = jwt

afterEach(() => {
  jest.clearAllMocks()
})

describe('UserService.authenticate', () => {
  let service: UserService

  beforeEach(() => {
    service = new UserService()
  })

  it('returns false when password length is less than 4', () => {
    const result = service.authenticate('user', '123')
    expect(result).toBe(false)
  })

  it('returns true when password length is exactly 4', () => {
    const result = service.authenticate('user', '1234')
    expect(result).toBe(true)
  })

  it('returns true when password length is greater than 4', () => {
    const result = service.authenticate('user', 'longpassword')
    expect(result).toBe(true)
  })

  it('does not check username at all', () => {
    const result1 = service.authenticate('user1', 'abcd')
    const result2 = service.authenticate('user2', 'abcd')
    expect(result1).toBe(true)
    expect(result2).toBe(true)
  })

  it('treats empty password as invalid', () => {
    const result = service.authenticate('user', '')
    expect(result).toBe(false)
  })
})

describe('UserService.deleteUser', () => {
  let service: UserService

  beforeEach(() => {
    service = new UserService()
  })

  it('calls database.delete with the correct user path', () => {
    service.deleteUser('123')
    expect(database.delete).toHaveBeenCalledTimes(1)
    expect(database.delete).toHaveBeenCalledWith('users/123')
  })

  it('allows deleting different userIds without any authorization checks', () => {
    service.deleteUser('abc')
    service.deleteUser('def')
    expect(database.delete).toHaveBeenNthCalledWith(1, 'users/abc')
    expect(database.delete).toHaveBeenNthCalledWith(2, 'users/def')
  })

  it('passes exactly the interpolated path string to database.delete', () => {
    const userId = 'user-with-special_chars-123'
    service.deleteUser(userId)
    expect(database.delete).toHaveBeenCalledWith(`users/${userId}`)
  })
})

describe('UserService.isAdmin', () => {
  let service: UserService

  beforeEach(() => {
    service = new UserService()
  })

  it('returns true when role is exactly "admin"', () => {
    const result = service.isAdmin({ role: 'admin' })
    expect(result).toBe(true)
  })

  it('returns false when role is not "admin"', () => {
    const result = service.isAdmin({ role: 'user' })
    expect(result).toBe(false)
  })

  it('uses loose equality so numeric 0 compared to "admin" is false', () => {
    const result = service.isAdmin({ role: 0 })
    expect(result).toBe(false)
  })

  it('returns false when role is undefined', () => {
    const result = service.isAdmin({})
    expect(result).toBe(false)
  })

  it('treats string "Admin" (different case) as non-admin', () => {
    const result = service.isAdmin({ role: 'Admin' })
    expect(result).toBe(false)
  })

  it('treats truthy non-admin values as non-admin', () => {
    const result = service.isAdmin({ role: true })
    expect(result).toBe(false)
  })
})

describe('UserService.validateToken', () => {
  let service: UserService

  beforeEach(() => {
    service = new UserService()
  })

  it('returns true when jwt.decode returns a non-null value', () => {
    jwt.decode = jest.fn().mockReturnValue({ sub: '123' })
    const result = service.validateToken('valid-token')
    expect(jwt.decode).toHaveBeenCalledTimes(1)
    expect(jwt.decode).toHaveBeenCalledWith('valid-token')
    expect(result).toBe(true)
  })

  it('returns false when jwt.decode returns null', () => {
    jwt.decode = jest.fn().mockReturnValue(null)
    const result = service.validateToken('invalid-token')
    expect(jwt.decode).toHaveBeenCalledTimes(1)
    expect(jwt.decode).toHaveBeenCalledWith('invalid-token')
    expect(result).toBe(false)
  })

  it('propagates exceptions thrown by jwt.decode', () => {
    const error = new Error('decode failed')
    jwt.decode = jest.fn(() => {
      throw error
    })
    expect(() => service.validateToken('bad-token')).toThrow(error)
    expect(jwt.decode).toHaveBeenCalledWith('bad-token')
  })

  it('treats any non-null decoded value as valid, including empty object', () => {
    jwt.decode = jest.fn().mockReturnValue({})
    const result = service.validateToken('token-with-empty-payload')
    expect(result).toBe(true)
  })

  it('treats non-object decoded values (like string) as valid as long as not null', () => {
    jwt.decode = jest.fn().mockReturnValue('some-payload')
    const result = service.validateToken('string-payload-token')
    expect(result).toBe(true)
  })
})

describe('UserService integration of methods behavior', () => {
  let service: UserService

  beforeEach(() => {
    service = new UserService()
  })

  it('can authenticate and then delete a user without any relation between them', () => {
    const authResult = service.authenticate('user', 'abcd')
    service.deleteUser('some-user-id')
    expect(authResult).toBe(true)
    expect(database.delete).toHaveBeenCalledWith('users/some-user-id')
  })

  it('validateToken does not check for expiration or specific claims', () => {
    jwt.decode = jest.fn().mockReturnValue({ exp: 0 })
    const result = service.validateToken('expired-token')
    expect(result).toBe(true)
    expect(jwt.decode).toHaveBeenCalledWith('expired-token')
  })
})