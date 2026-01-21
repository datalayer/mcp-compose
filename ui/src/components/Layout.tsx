/*
 * Copyright (c) 2023-2025 Datalayer, Inc.
 * Distributed under the terms of the Modified BSD License.
 */

import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Box, NavList, Button, useTheme } from '@primer/react'
import { 
  SunIcon, 
  MoonIcon,
  HomeIcon,
  ServerIcon,
  ToolsIcon,
  FileCodeIcon,
  SyncIcon,
  FileIcon,
  GraphIcon,
  GearIcon,
  SignOutIcon,
} from '@primer/octicons-react'
import { useAuth } from '../store/auth'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: HomeIcon },
  { name: 'Servers', href: '/servers', icon: ServerIcon },
  { name: 'Tools', href: '/tools', icon: ToolsIcon },
  { name: 'Configuration', href: '/configuration', icon: FileCodeIcon },
  { name: 'Translators', href: '/translators', icon: SyncIcon },
  { name: 'Logs', href: '/logs', icon: FileIcon },
  { name: 'Metrics', href: '/metrics', icon: GraphIcon },
  { name: 'Settings', href: '/settings', icon: GearIcon },
]

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { logout } = useAuth()
  const { colorMode, setColorMode } = useTheme()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const toggleTheme = () => {
    setColorMode(colorMode === 'day' ? 'night' : 'day')
  }

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <Box
        sx={{
          width: 256,
          borderRight: '1px solid',
          borderColor: 'border.default',
          bg: 'canvas.subtle',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Logo */}
        <Box
          sx={{
            p: 3,
            borderBottom: '1px solid',
            borderColor: 'border.default',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Box sx={{ fontSize: 2, fontWeight: 'bold' }}>
            MCP Compose
          </Box>
          <Button
            onClick={toggleTheme}
            variant="invisible"
            aria-label="Toggle theme"
            sx={{ p: 2 }}
          >
            {colorMode === 'day' ? <MoonIcon /> : <SunIcon />}
          </Button>
        </Box>

        {/* Navigation */}
        <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
          <NavList>
            {navigation.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname === item.href
              
              return (
                <NavList.Item
                  key={item.name}
                  href={item.href}
                  aria-current={isActive ? 'page' : undefined}
                  onClick={(e) => {
                    e.preventDefault()
                    navigate(item.href)
                  }}
                >
                  <NavList.LeadingVisual>
                    <Icon />
                  </NavList.LeadingVisual>
                  {item.name}
                </NavList.Item>
              )
            })}
          </NavList>
        </Box>

        {/* Logout button */}
        <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'border.default' }}>
          <Button
            onClick={handleLogout}
            variant="invisible"
            block
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-start',
              color: 'fg.muted',
              '&:hover': {
                color: 'fg.default',
              },
            }}
          >
            <SignOutIcon />
            <Box sx={{ ml: 2 }}>Sign out</Box>
          </Button>
        </Box>
      </Box>

      {/* Main content */}
      <Box sx={{ flex: 1, overflow: 'auto', bg: 'canvas.default' }}>
        <Box sx={{ p: 4 }}>
          <Outlet />
        </Box>
      </Box>
    </Box>
  )
}
