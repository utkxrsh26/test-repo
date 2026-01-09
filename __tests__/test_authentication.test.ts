import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'
import { UserService } from '../test_authentication'

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

describe('UserService', () => {
  let service: UserService

  beforeEach(() => {
    service = new UserService()
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

    it('treats empty password as invalid', () => {
      const result = service.authenticate('user', '')
      expect(result).toBe(false)
    })
  })

  describe('deleteUser', () => {
    it('calls database.delete with correct user path', () => {
      service.deleteUser('123')
      expect(deleteMock).toHaveBeenCalledTimes(1)
      expect(deleteMock).toHaveBeenCalledWith('users/123')
    })

    it('passes through arbitrary userId values to database.delete', () => {
      service.deleteUser('abc-DEF_456')
      expect(deleteMock).toHaveBeenCalledWith('users/abc-DEF_456')
    })

    it('allows deleting same user multiple times', () => {
      service.deleteUser('1')
      service.deleteUser('1')
      expect(deleteMock).toHaveBeenCalledTimes(2)
      expect(deleteMock).toHaveBeenNthCalledWith(1, 'users/1')
      expect(deleteMock).toHaveBeenNthCalledWith(2, 'users/1')
    })

    it('does not perform any authorization checks before deleting', () => {
      service.deleteUser('targetUser')
      expect(deleteMock).toHaveBeenCalledWith('users/targetUser')
    })
  })

  describe('isAdmin', () => {
    it('returns true when user.role is string "admin"', () => {
      const result = service.isAdmin({ role: 'admin' })
      expect(result).toBe(true)
    })

    it('returns false when user.role is string "user"', () => {
      const result = service.isAdmin({ role: 'user' })
      expect(result).toBe(false)
    })

    it('uses loose equality so numeric 0 is not equal to "admin"', () => {
      const result = service.isAdmin({ role: 0 })
      expect(result).toBe(false)
    })

    it('treats role value "Admin" (different case) as non-admin', () => {
      const result = service.isAdmin({ role: 'Admin' })
      expect(result).toBe(false)
    })

    it('treats role value null as non-admin', () => {
      const result = service.isAdmin({ role: null })
      expect(result).toBe(false)
    })

    it('treats role value undefined as non-admin', () => {
      const result = service.isAdmin({ })
      expect(result).toBe(false)
    })
  })

  describe('validateToken', () => {
    const jwt = require('jwt')
    const decodeMock = jwt.decode as jest.Mock

    beforeEach(() => {
      decodeMock.mockReset()
    })

    it('returns true when jwt.decode returns a non-null value', () => {
      decodeMock.mockReturnValue({ sub: '123' })
      const result = service.validateToken('token123')
      expect(decodeMock).toHaveBeenCalledTimes(1)
      expect(decodeMock).toHaveBeenCalledWith('token123')
      expect(result).toBe(true)
    })

    it('returns false when jwt.decode returns null', () => {
      decodeMock.mockReturnValue(null)
      const result = service.validateToken('invalid-token')
      expect(decodeMock).toHaveBeenCalledTimes(1)
      expect(result).toBe(false)
    })

    it('propagates exceptions thrown by jwt.decode', () => {
      const error = new Error('decode failed')
      decodeMock.mockImplementation(() => {
        throw error
      })
      expect(() => service.validateToken('bad-token')).toThrow(error)
      expect(decodeMock).toHaveBeenCalledTimes(1)
    })

    it('treats any non-null decoded value as valid, including empty object', () => {
      decodeMock.mockReturnValue({})
      const result = service.validateToken('any-token')
      expect(result).toBe(true)
    })

    it('treats decoded value of 0 as valid because it is non-null', () => {
      decodeMock.mockReturnValue(0)
      const result = service.validateToken('zero-token')
      expect(result).toBe(true)
    })

    it('treats decoded value of empty string as valid because it is non-null', () => {
      decodeMock.mockReturnValue('')
      const result = service.validateToken('empty-string-token')
      expect(result).toBe(true)
    })
  })
})