/*
 * Copyright (c) 2023-2025 Datalayer, Inc.
 * Distributed under the terms of the Modified BSD License.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, FormControl, TextInput, Flash, Heading } from '@primer/react'
import { useMutation } from '@tanstack/react-query'
import { LockIcon } from '@primer/octicons-react'
import api from '../api/client'
import { useAuth } from '../store/auth'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const { login } = useAuth()

  const loginMutation = useMutation({
    mutationFn: async () => {
      const response = await api.login(username, password)
      return response.data
    },
    onSuccess: (data) => {
      login(data.token, data.user_id)
      navigate('/dashboard')
    },
    onError: (error: unknown) => {
      const err = error as { response?: { data?: { detail?: string } } }
      setError(err.response?.data?.detail || 'Login failed')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!username || !password) return
    setError('')
    loginMutation.mutate()
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        backgroundColor: 'var(--bgColor-default)',
      }}
    >
      <form
        onSubmit={handleSubmit}
        style={{
          width: '100%',
          maxWidth: '400px',
          padding: '32px',
          backgroundColor: 'var(--bgColor-muted)',
          borderRadius: '6px',
          border: '1px solid var(--borderColor-default)',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <LockIcon size={48} />
          <Heading sx={{ mt: 3, mb: 2 }}>MCP Compose</Heading>
          <div style={{ color: 'var(--fgColor-muted)' }}>Sign in to your account</div>
        </div>

        {error && (
          <Flash variant="danger" sx={{ mb: 3 }}>
            {error}
          </Flash>
        )}

        <FormControl required sx={{ mb: 3 }}>
          <FormControl.Label>Username</FormControl.Label>
          <TextInput
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Enter username"
            autoComplete="username"
            block
            disabled={loginMutation.isPending}
          />
        </FormControl>

        <FormControl required sx={{ mb: 4 }}>
          <FormControl.Label>Password</FormControl.Label>
          <TextInput
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter password"
            autoComplete="current-password"
            block
            disabled={loginMutation.isPending}
          />
        </FormControl>

        <Button
          type="submit"
          variant="primary"
          block
          disabled={loginMutation.isPending || !username || !password}
          sx={{ mb: 2 }}
        >
          {loginMutation.isPending ? 'Signing in...' : 'Sign in'}
        </Button>
      </form>
    </div>
  )
}
