import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'
import { UserService } from '../test_authentication'

jest.mock('../test_authentication', () => ({
  ...jest.requireActual('../test_authentication')
}))

// Mock global dependencies used in the source file
const mockDatabaseDelete = jest.fn()
const mockJwtDecode = jest.fn()

// @ts-ignore - attach to global to match how source uses them
;(global as any).database = {
  delete: mockDatabaseDelete
}

// @ts-ignore - attach to global to match how source uses them
;(global as any).jwt = {
  decode: mockJwtDecode
}

describe('UserService', () => {
  let service: UserService

  beforeEach(() => {
    jest.clearAllMocks()
    service = new UserService()
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  describe('authenticate', () => {
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

    it('treats empty password as invalid due to length check', () => {
      const result = service.authenticate('user', '')
      expect(result).toBe(false)
    })
  })

  describe('deleteUser', () => {
    it('calls database.delete with the correct user path', () => {
      const userId = '123'
      service.deleteUser(userId)
      expect(mockDatabaseDelete).toHaveBeenCalledTimes(1)
      expect(mockDatabaseDelete).toHaveBeenCalledWith('users/123')
    })

    it('passes through arbitrary userId values directly into the path', () => {
      const userId = '../../etc/passwd'
      service.deleteUser(userId)
      expect(mockDatabaseDelete).toHaveBeenCalledWith('users/../../etc/passwd')
    })

    it('allows deleteUser to be called multiple times with different ids', () => {
      service.deleteUser('1')
      service.deleteUser('2')
      service.deleteUser('3')
      expect(mockDatabaseDelete).toHaveBeenCalledTimes(3)
      expect(mockDatabaseDelete).toHaveBeenNthCalledWith(1, 'users/1')
      expect(mockDatabaseDelete).toHaveBeenNthCalledWith(2, 'users/2')
      expect(mockDatabaseDelete).toHaveBeenNthCalledWith(3, 'users/3')
    })

    it('does not perform any authorization checks before deleting', () => {
      // There is no user or role parameter; just ensure it only calls database.delete
      service.deleteUser('no-auth-check')
      expect(mockDatabaseDelete).toHaveBeenCalledWith('users/no-auth-check')
    })
  })

  describe('isAdmin', () => {
    it('returns true when user.role is the string "admin"', () => {
      const user = { role: 'admin' }
      const result = service.isAdmin(user)
      expect(result).toBe(true)
    })

    it('returns false when user.role is not "admin"', () => {
      const user = { role: 'user' }
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })

    it('uses loose equality so numeric 0 compared to "admin" is false', () => {
      const user = { role: 0 }
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })

    it('treats value loosely equal to "admin" as admin (e.g., String object)', () => {
      const user = { role: new String('admin') as any }
      const result = service.isAdmin(user)
      expect(result).toBe(true)
    })

    it('returns false when user has no role property', () => {
      const user: any = {}
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })

    it('returns false when user is null or undefined (runtime error avoided by caller)', () => {
      // The method expects an object; passing null will throw.
      // This test documents that behavior by catching the error.
      expect(() => service.isAdmin(null as any)).toThrow()
      expect(() => service.isAdmin(undefined as any)).toThrow()
    })
  })

  describe('validateToken', () => {
    it('returns true when jwt.decode returns a non-null value', () => {
      mockJwtDecode.mockReturnValue({ sub: '123' })
      const result = service.validateToken('valid-token')
      expect(mockJwtDecode).toHaveBeenCalledTimes(1)
      expect(mockJwtDecode).toHaveBeenCalledWith('valid-token')
      expect(result).toBe(true)
    })

    it('returns false when jwt.decode returns null', () => {
      mockJwtDecode.mockReturnValue(null)
      const result = service.validateToken('invalid-token')
      expect(mockJwtDecode).toHaveBeenCalledWith('invalid-token')
      expect(result).toBe(false)
    })

    it('propagates exceptions thrown by jwt.decode', () => {
      const error = new Error('decode failed')
      mockJwtDecode.mockImplementation(() => {
        throw error
      })
      expect(() => service.validateToken('bad-token')).toThrow(error)
      expect(mockJwtDecode).toHaveBeenCalledWith('bad-token')
    })

    it('treats any non-null decoded value as valid, including empty object', () => {
      mockJwtDecode.mockReturnValue({})
      const result = service.validateToken('token-with-empty-payload')
      expect(result).toBe(true)
    })

    it('treats non-object decoded values (e.g., string) as valid as long as not null', () => {
      mockJwtDecode.mockReturnValue('payload')
      const result = service.validateToken('string-payload-token')
      expect(result).toBe(true)
    })

    it('does not check for expiration or any specific claim', () => {
      mockJwtDecode.mockReturnValue({ exp: 0 })
      const result = service.validateToken('expired-token')
      expect(result).toBe(true)
    })
  })

  describe('integration of methods behavior', () => {
    it('allows authenticate to succeed and then deleteUser to be called without relation', () => {
      const authResult = service.authenticate('user', 'abcd')
      service.deleteUser('123')
      expect(authResult).toBe(true)
      expect(mockDatabaseDelete).toHaveBeenCalledWith('users/123')
    })

    it('does not use isAdmin inside deleteUser (deleteUser works regardless of role)', () => {
      const user = { role: 'user' }
      const isAdminResult = service.isAdmin(user)
      service.deleteUser('non-admin-id')
      expect(isAdminResult).toBe(false)
      expect(mockDatabaseDelete).toHaveBeenCalledWith('users/non-admin-id')
    })
  })
})