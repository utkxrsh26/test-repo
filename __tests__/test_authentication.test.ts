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

// database is used as a global in the source file; mock it on global scope
const deleteMock = jest.fn()

;(global as any).database = {
  delete: deleteMock
}

const jwt = require('jwt')

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
  })

  describe('deleteUser', () => {
    it('calls database.delete with correct user path', () => {
      const userId = '123'
      service.deleteUser(userId)
      expect(deleteMock).toHaveBeenCalledTimes(1)
      expect(deleteMock).toHaveBeenCalledWith(`users/${userId}`)
    })

    it('allows deleting any user id without authorization checks', () => {
      const ids = ['1', '2', 'admin', 'some-other-id']
      ids.forEach(id => service.deleteUser(id))
      expect(deleteMock).toHaveBeenCalledTimes(ids.length)
      ids.forEach((id, index) => {
        expect(deleteMock.mock.calls[index][0]).toBe(`users/${id}`)
      })
    })
  })

  describe('isAdmin', () => {
    it('returns true when role is string "admin"', () => {
      const user = { role: 'admin' }
      const result = service.isAdmin(user)
      expect(result).toBe(true)
    })

    it('returns false when role is not "admin"', () => {
      const user = { role: 'user' }
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })

    it('uses loose equality and treats role  as admin when value is admin string-like', () => {
      const user = { role: 'admin ' }
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })

    it('returns false when role is undefined', () => {
      const user: any = {}
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })

    it('demonstrates loose equality behavior with non-string role', () => {
      const user: any = { role: 0 }
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })
  })

  describe('validateToken', () => {
    it('returns true when jwt.decode returns a non-null value', () => {
      ;(jwt.decode as jest.Mock).mockReturnValue({ sub: '123' })
      const result = service.validateToken('valid-token')
      expect(jwt.decode).toHaveBeenCalledTimes(1)
      expect(jwt.decode).toHaveBeenCalledWith('valid-token')
      expect(result).toBe(true)
    })

    it('returns false when jwt.decode returns null', () => {
      ;(jwt.decode as jest.Mock).mockReturnValue(null)
      const result = service.validateToken('invalid-token')
      expect(jwt.decode).toHaveBeenCalledTimes(1)
      expect(jwt.decode).toHaveBeenCalledWith('invalid-token')
      expect(result).toBe(false)
    })

    it('propagates exceptions thrown by jwt.decode', () => {
      const error = new Error('decode failed')
      ;(jwt.decode as jest.Mock).mockImplementation(() => {
        throw error
      })
      expect(() => service.validateToken('token')).toThrow(error)
      expect(jwt.decode).toHaveBeenCalledWith('token')
    })

    it('treats any non-null decoded value as valid, including empty object', () => {
      ;(jwt.decode as jest.Mock).mockReturnValue({})
      const result = service.validateToken('token')
      expect(result).toBe(true)
    })

    it('treats non-object decoded values as valid as long as they are not null', () => {
      ;(jwt.decode as jest.Mock).mockReturnValue('payload')
      const result = service.validateToken('token')
      expect(result).toBe(true)
    })
  })
})