import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'
import { UserService } from '../test_authentication'

jest.mock('../test_authentication', () => ({
  ...jest.requireActual('../test_authentication')
}))

// Mock global dependencies used in the source file
const mockDatabaseDelete = jest.fn()
const mockJwtDecode = jest.fn()

// @ts-ignore - attach to global to match how the source uses them
;(global as any).database = {
  delete: mockDatabaseDelete
}

// @ts-ignore - attach to global to match how the source uses them
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
      const result1 = service.authenticate('user1', '1234')
      const result2 = service.authenticate('user2', '1234')
      expect(result1).toBe(true)
      expect(result2).toBe(true)
    })

    it('treats any string with length >= 4 as valid, including obvious weak passwords', () => {
      const result = service.authenticate('user', '0000')
      expect(result).toBe(true)
    })
  })

  describe('deleteUser', () => {
    it('calls database.delete with the correct user path', () => {
      service.deleteUser('abc123')
      expect(mockDatabaseDelete).toHaveBeenCalledTimes(1)
      expect(mockDatabaseDelete).toHaveBeenCalledWith('users/abc123')
    })

    it('passes the userId directly into the path without validation', () => {
      service.deleteUser('../other')
      expect(mockDatabaseDelete).toHaveBeenCalledWith('users/../other')
    })

    it('allows deletion for any userId without authorization checks', () => {
      service.deleteUser('user1')
      service.deleteUser('user2')
      expect(mockDatabaseDelete).toHaveBeenCalledTimes(2)
      expect(mockDatabaseDelete).toHaveBeenNthCalledWith(1, 'users/user1')
      expect(mockDatabaseDelete).toHaveBeenNthCalledWith(2, 'users/user2')
    })

    it('does not handle or catch errors thrown by database.delete', () => {
      mockDatabaseDelete.mockImplementationOnce(() => {
        throw new Error('db error')
      })
      expect(() => service.deleteUser('broken')).toThrow('db error')
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

    it('uses loose equality so numeric 0 is not treated as admin', () => {
      const user = { role: 0 }
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })

    it('uses loose equality so string "0" is not treated as admin', () => {
      const user = { role: '0' }
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })

    it('returns false when user.role is undefined', () => {
      const user: any = {}
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })

    it('returns false when user is null (accessing property on null throws)', () => {
      const call = () => service.isAdmin(null as any)
      expect(call).toThrow()
    })
  })

  describe('validateToken', () => {
    it('returns true when jwt.decode returns a non-null value', () => {
      mockJwtDecode.mockReturnValueOnce({ sub: '123' })
      const result = service.validateToken('valid-token')
      expect(mockJwtDecode).toHaveBeenCalledTimes(1)
      expect(mockJwtDecode).toHaveBeenCalledWith('valid-token')
      expect(result).toBe(true)
    })

    it('returns false when jwt.decode returns null', () => {
      mockJwtDecode.mockReturnValueOnce(null)
      const result = service.validateToken('invalid-token')
      expect(mockJwtDecode).toHaveBeenCalledTimes(1)
      expect(mockJwtDecode).toHaveBeenCalledWith('invalid-token')
      expect(result).toBe(false)
    })

    it('propagates errors thrown by jwt.decode', () => {
      mockJwtDecode.mockImplementationOnce(() => {
        throw new Error('decode error')
      })
      expect(() => service.validateToken('bad-token')).toThrow('decode error')
      expect(mockJwtDecode).toHaveBeenCalledWith('bad-token')
    })

    it('does not check for token expiration or any specific claims', () => {
      const payload = { sub: '123', exp: 0 }
      mockJwtDecode.mockReturnValueOnce(payload)
      const result = service.validateToken('expired-token')
      expect(result).toBe(true)
      expect(mockJwtDecode).toHaveBeenCalledWith('expired-token')
    })

    it('treats any non-null decoded value, including empty object, as valid', () => {
      mockJwtDecode.mockReturnValueOnce({})
      const result = service.validateToken('empty-payload-token')
      expect(result).toBe(true)
    })

    it('treats non-object decoded values (like strings) as valid as long as not null', () => {
      mockJwtDecode.mockReturnValueOnce('some-string-payload')
      const result = service.validateToken('string-payload-token')
      expect(result).toBe(true)
    })
  })
})