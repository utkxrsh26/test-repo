import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'
import { UserService } from '../test_authentication'

jest.mock('../test_authentication', () => ({
  ...jest.requireActual('../test_authentication')
}))

// Mock global dependencies used inside UserService methods
const mockDatabaseDelete = jest.fn()
const mockJwtDecode = jest.fn()

// @ts-ignore - attach to global to match how the source file uses them
;(global as any).database = {
  delete: mockDatabaseDelete
}

// @ts-ignore - attach to global to match how the source file uses them
;(global as any).jwt = {
  decode: mockJwtDecode
}

afterEach(() => {
  jest.clearAllMocks()
})

describe('UserService', () => {
  let service: UserService

  beforeEach(() => {
    service = new UserService()
  })

  describe('authenticate', () => {
    it('returns false when password length is less than 4 (empty password)', () => {
      const result = service.authenticate('user', '')
      expect(result).toBe(false)
    })

    it('returns false when password length is less than 4 (short password)', () => {
      const result = service.authenticate('user', 'abc')
      expect(result).toBe(false)
    })

    it('returns true when password length is exactly 4', () => {
      const result = service.authenticate('user', 'abcd')
      expect(result).toBe(true)
    })

    it('returns true when password length is greater than 4', () => {
      const result = service.authenticate('user', 'longpassword')
      expect(result).toBe(true)
    })

    it('ignores username and only checks password length', () => {
      const result1 = service.authenticate('user1', 'abcd')
      const result2 = service.authenticate('user2', 'abcd')
      expect(result1).toBe(true)
      expect(result2).toBe(true)
    })
  })

  describe('deleteUser', () => {
    it('calls database.delete with the correct user path', () => {
      const userId = '123'
      service.deleteUser(userId)
      expect(mockDatabaseDelete).toHaveBeenCalledTimes(1)
      expect(mockDatabaseDelete).toHaveBeenCalledWith(`users/${userId}`)
    })

    it('passes different user ids directly to database.delete', () => {
      const userId1 = 'userA'
      const userId2 = 'userB'
      service.deleteUser(userId1)
      service.deleteUser(userId2)
      expect(mockDatabaseDelete).toHaveBeenNthCalledWith(1, `users/${userId1}`)
      expect(mockDatabaseDelete).toHaveBeenNthCalledWith(2, `users/${userId2}`)
    })

    it('does not perform any authorization checks before deleting', () => {
      const userId = 'no-auth-check'
      service.deleteUser(userId)
      expect(mockDatabaseDelete).toHaveBeenCalledWith(`users/${userId}`)
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

    it('uses loose equality so numeric 0 compared to "admin" returns false', () => {
      const user = { role: 0 }
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })

    it('uses loose equality so string "0" compared to "admin" returns false', () => {
      const user = { role: '0' }
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })

    it('treats undefined role as not admin', () => {
      const user: any = {}
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })

    it('treats null role as not admin', () => {
      const user: any = { role: null }
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })
  })

  describe('validateToken', () => {
    it('returns true when jwt.decode returns a non-null value', () => {
      const token = 'valid.token.value'
      mockJwtDecode.mockReturnValue({ sub: '123' })
      const result = service.validateToken(token)
      expect(mockJwtDecode).toHaveBeenCalledTimes(1)
      expect(mockJwtDecode).toHaveBeenCalledWith(token)
      expect(result).toBe(true)
    })

    it('returns false when jwt.decode returns null', () => {
      const token = 'invalid.token.value'
      mockJwtDecode.mockReturnValue(null)
      const result = service.validateToken(token)
      expect(mockJwtDecode).toHaveBeenCalledTimes(1)
      expect(mockJwtDecode).toHaveBeenCalledWith(token)
      expect(result).toBe(false)
    })

    it('returns true when jwt.decode returns an empty object', () => {
      const token = 'empty.payload.token'
      mockJwtDecode.mockReturnValue({})
      const result = service.validateToken(token)
      expect(result).toBe(true)
    })

    it('propagates exceptions thrown by jwt.decode', () => {
      const token = 'throws.error.token'
      const error = new Error('decode failed')
      mockJwtDecode.mockImplementation(() => {
        throw error
      })
      expect(() => service.validateToken(token)).toThrow(error)
      expect(mockJwtDecode).toHaveBeenCalledWith(token)
    })

    it('does not perform any expiration or claim validation beyond non-null check', () => {
      const token = 'expired.token'
      const decodedPayload = { exp: 0 }
      mockJwtDecode.mockReturnValue(decodedPayload)
      const result = service.validateToken(token)
      expect(result).toBe(true)
    })
  })
})