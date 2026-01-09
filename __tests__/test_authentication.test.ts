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

const mockedJwt = jest.requireMock('jwt') as { decode: jest.Mock }

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

    it('treats empty password as invalid even with any username', () => {
      const result = service.authenticate('anyuser', '')
      expect(result).toBe(false)
    })
  })

  describe('deleteUser', () => {
    it('calls database.delete with the correct user path', () => {
      service.deleteUser('123')
      expect(deleteMock).toHaveBeenCalledTimes(1)
      expect(deleteMock).toHaveBeenCalledWith('users/123')
    })

    it('allows deleting different user ids without any authorization checks', () => {
      service.deleteUser('userA')
      service.deleteUser('userB')
      expect(deleteMock).toHaveBeenNthCalledWith(1, 'users/userA')
      expect(deleteMock).toHaveBeenNthCalledWith(2, 'users/userB')
    })

    it('passes exactly the concatenated path string to database.delete', () => {
      const userId = 'some-special_id-42'
      service.deleteUser(userId)
      expect(deleteMock).toHaveBeenCalledWith(`users/${userId}`)
    })
  })

  describe('isAdmin', () => {
    it('returns true when role is the string "admin"', () => {
      const user = { role: 'admin' }
      const result = service.isAdmin(user)
      expect(result).toBe(true)
    })

    it('returns false when role is not "admin"', () => {
      const user = { role: 'user' }
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })

    it('uses loose equality so numeric 0 does not equal "admin"', () => {
      const user = { role: 0 }
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })

    it('uses loose equality so string "0" does not equal "admin"', () => {
      const user = { role: '0' }
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })

    it('treats undefined role as non-admin', () => {
      const user: any = {}
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })

    it('treats null role as non-admin', () => {
      const user: any = { role: null }
      const result = service.isAdmin(user)
      expect(result).toBe(false)
    })
  })

  describe('validateToken', () => {
    it('returns true when jwt.decode returns a non-null value', () => {
      mockedJwt.decode.mockReturnValueOnce({ sub: '123' })
      const result = service.validateToken('valid-token')
      expect(mockedJwt.decode).toHaveBeenCalledTimes(1)
      expect(mockedJwt.decode).toHaveBeenCalledWith('valid-token')
      expect(result).toBe(true)
    })

    it('returns false when jwt.decode returns null', () => {
      mockedJwt.decode.mockReturnValueOnce(null)
      const result = service.validateToken('invalid-token')
      expect(mockedJwt.decode).toHaveBeenCalledTimes(1)
      expect(mockedJwt.decode).toHaveBeenCalledWith('invalid-token')
      expect(result).toBe(false)
    })

    it('propagates exceptions thrown by jwt.decode', () => {
      const error = new Error('decode failed')
      mockedJwt.decode.mockImplementationOnce(() => {
        throw error
      })
      expect(() => service.validateToken('bad-token')).toThrow(error)
      expect(mockedJwt.decode).toHaveBeenCalledWith('bad-token')
    })

    it('treats any truthy decoded payload as valid', () => {
      mockedJwt.decode.mockReturnValueOnce(0 as any)
      const result = service.validateToken('token-with-zero-payload')
      expect(result).toBe(false)

      mockedJwt.decode.mockReturnValueOnce('payload' as any)
      const result2 = service.validateToken('token-with-string-payload')
      expect(result2).toBe(true)
    })

    it('can be called multiple times with different tokens', () => {
      mockedJwt.decode
        .mockReturnValueOnce({ sub: '1' })
        .mockReturnValueOnce(null)
        .mockReturnValueOnce({ sub: '3' })

      const r1 = service.validateToken('t1')
      const r2 = service.validateToken('t2')
      const r3 = service.validateToken('t3')

      expect(r1).toBe(true)
      expect(r2).toBe(false)
      expect(r3).toBe(true)
      expect(mockedJwt.decode).toHaveBeenNthCalledWith(1, 't1')
      expect(mockedJwt.decode).toHaveBeenNthCalledWith(2, 't2')
      expect(mockedJwt.decode).toHaveBeenNthCalledWith(3, 't3')
    })
  })
})