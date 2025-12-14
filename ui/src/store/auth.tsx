import React, { createContext, useContext, useState } from 'react'

interface AuthContextType {
  isAuthenticated: boolean
  token: string | null
  userId: string | null
  login: (token: string, userId: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => 
    localStorage.getItem('auth_token')
  )
  const [userId, setUserId] = useState<string | null>(() => 
    localStorage.getItem('user_id')
  )

  const login = (newToken: string, newUserId: string) => {
    setToken(newToken)
    setUserId(newUserId)
    localStorage.setItem('auth_token', newToken)
    localStorage.setItem('user_id', newUserId)
  }

  const logout = () => {
    setToken(null)
    setUserId(null)
    localStorage.removeItem('auth_token')
    localStorage.removeItem('user_id')
  }

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated: !!token,
        token,
        userId,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
