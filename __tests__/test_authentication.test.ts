import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'
import { UserService } from '../test_authentication'

jest.mock('../test_authentication', () => {
  const actual = jest.requireActual('../test_authentication')
  return {
    ...actual
  }
})

describe('UserService', () => {
  let userService: UserService
  let originalDatabase: any
  let originalJwt: any

  beforeEach(() => {
    userService = new UserService()

    // Save originals if they exist
    // @ts-ignore
    originalDatabase = (global as any).database
    // @ts-ignore
    originalJwt = (global as any).jwt

    // Mock global database with delete method
    ;(global as any).database = {
      delete: jest.fn()
    }

    // Mock global jwt with decode method
    ;(global as any).jwt = {
      decode: jest.fn()
    }
  })

  afterEach(() => {
    jest.clearAllMocks()
    // Restore globals
    // @ts-ignore
    ;(global as any).database = originalDatabase
    // @ts-ignore
    ;(global as any).jwt = originalJwt
  })

  describe('authenticate', () => {
    it('returns false when password length is less than 4', () => {
      const result = userService.authenticate('user', '123')
      expect(result).toBe(false)
    })

    it('returns true when password length is exactly 4', () => {
      const result = userService.authenticate('user', '1234')
      expect(result).toBe(true)
    })

    it('returns true when password length is greater than 4', () => {
      const result = userService.authenticate('user', 'longpassword')
      expect(result).toBe(true)
    })

    it('does not check username at all', () => {
      const result1 = userService.authenticate('user1', 'abcd')
      const result2 = userService.authenticate('anotherUser', 'abcd')
      expect(result1).toBe(true)
      expect(result2).toBe(true)
    })

    it('treats any non-empty string of length >= 4 as valid password', () => {
      const passwords = ['0000', '    ', 'pass', 'p@$$', '12345']
      const results = passwords.map(pw => userService.authenticate('user', pw))
      results.forEach(res => expect(res).toBe(true))
    })
  })

  describe('deleteUser', () => {
    it('calls database.delete with the correct user path', () => {
      const db = (global as any).database
      userService.deleteUser('123')
      expect(db.delete).toHaveBeenCalledTimes(1)
      expect(db.delete).toHaveBeenCalledWith('users/123')
    })

    it('passes the userId directly into the path without validation', () => {
      const db = (global as any).database
      userService.deleteUser('../admin')
      expect(db.delete).toHaveBeenCalledWith('users/../admin')
    })

    it('does not perform any authorization checks before deleting', () => {
      const db = (global as any).database
      userService.deleteUser('any-user-id')
      expect(db.delete).toHaveBeenCalled()
    })

    it('propagates errors thrown by database.delete', () => {
      const db = (global as any).database
      ;(db.delete as jest.Mock).mockImplementation(() => {
        throw new Error('delete failed')
      })
      expect(() => userService.deleteUser('123')).toThrow('delete failed')
    })
  })

  describe('isAdmin', () => {
    it('returns true when role is exactly "admin"', () => {
      const result = userService.isAdmin({ role: 'admin' })
      expect(result).toBe(true)
    })

    it('returns false when role is not "admin"', () => {
      const result = userService.isAdmin({ role: 'user' })
      expect(result).toBe(false)
    })

    it('uses loose equality so numeric 0 compared to "admin" is false', () => {
      const result = userService.isAdmin({ role: 0 })
      expect(result).toBe(false)
    })

    it('uses loose equality so string "0" compared to "admin" is false', () => {
      const result = userService.isAdmin({ role: '0' })
      expect(result).toBe(false)
    })

    it('returns false when user object has no role property', () => {
      const result = userService.isAdmin({})
      expect(result).toBe(false)
    })

    it('returns false when user is null or undefined', () => {
      const resultNull = userService.isAdmin(null as any)
      const resultUndefined = userService.isAdmin(undefined as any)
      expect(resultNull).toBe(false)
      expect(resultUndefined).toBe(false)
    })
  })

  describe('validateToken', () => {
    it('returns true when jwt.decode returns a non-null value', () => {
      const jwtMock = (global as any).jwt
      ;(jwtMock.decode as jest.Mock).mockReturnValue({ sub: '123' })
      const result = userService.validateToken('token')
      expect(jwtMock.decode).toHaveBeenCalledWith('token')
      expect(result).toBe(true)
    })

    it('returns false when jwt.decode returns null', () => {
      const jwtMock = (global as any).jwt
      ;(jwtMock.decode as jest.Mock).mockReturnValue(null)
      const result = userService.validateToken('invalid-token')
      expect(jwtMock.decode).toHaveBeenCalledWith('invalid-token')
      expect(result).toBe(false)
    })

    it('treats any non-null decoded value as valid, regardless of content', () => {
      const jwtMock = (global as any).jwt
      ;(jwtMock.decode as jest.Mock).mockReturnValue({})
      const resultEmpty = userService.validateToken('empty-payload')
      ;(jwtMock.decode as jest.Mock).mockReturnValue({ exp: 0 })
      const resultExpired = userService.validateToken('expired-token')
      expect(resultEmpty).toBe(true)
      expect(resultExpired).toBe(true)
    })

    it('does not handle exceptions thrown by jwt.decode', () => {
      const jwtMock = (global as any).jwt
      ;(jwtMock.decode as jest.Mock).mockImplementation(() => {
        throw new Error('decode error')
      })
      expect(() => userService.validateToken('bad-token')).toThrow('decode error')
    })

    it('calls jwt.decode exactly once per validateToken call', () => {
      const jwtMock = (global as any).jwt
      ;(jwtMock.decode as jest.Mock).mockReturnValue({ sub: '123' })
      userService.validateToken('token1')
      userService.validateToken('token2')
      expect(jwtMock.decode).toHaveBeenCalledTimes(2)
      expect(jwtMock.decode).toHaveBeenNthCalledWith(1, 'token1')
      expect(jwtMock.decode).toHaveBeenNthCalledWith(2, 'token2')
    })
  })
})