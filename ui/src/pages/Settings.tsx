import { useState } from 'react'
import { useThemeStore } from '../store/theme'
import { MoonIcon, SunIcon, BellIcon, CheckIcon } from '@primer/octicons-react'
import { Box, Heading, Text, Button, TextInput, FormControl, Checkbox, Select, Link } from '@primer/react'

export default function Settings() {
  const { theme, setTheme } = useThemeStore()
  const [apiEndpoint, setApiEndpoint] = useState('http://localhost:8000')
  const [refreshInterval, setRefreshInterval] = useState(5)
  const [enableNotifications, setEnableNotifications] = useState(true)
  const [enableSounds, setEnableSounds] = useState(false)
  const [maxLogLines, setMaxLogLines] = useState(500)
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    // In a real app, these would be persisted to localStorage or backend
    localStorage.setItem('settings', JSON.stringify({
      apiEndpoint,
      refreshInterval,
      enableNotifications,
      enableSounds,
      maxLogLines,
    }))
    
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  return (
    <Box>
      {/* Header */}
      <Box style={{ marginBottom: '24px' }}>
        <Heading style={{ fontSize: '32px', marginBottom: '8px' }}>Settings</Heading>
        <Text style={{ color: '#656d76' }}>Configure application preferences and behavior</Text>
      </Box>

      {/* Appearance */}
      <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa', marginBottom: '24px' }}>
        <Heading style={{ fontSize: '20px', marginBottom: '16px' }}>Appearance</Heading>
        
        <Box>
          <Text style={{ fontSize: '14px', fontWeight: '600', display: 'block', marginBottom: '12px' }}>Theme</Text>
          <Box style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
            <Box
              onClick={() => setTheme('light')}
              style={{
                padding: '16px',
                border: theme === 'light' ? '2px solid #0969da' : '2px solid #d0d7de',
                borderRadius: '6px',
                backgroundColor: theme === 'light' ? 'rgba(9, 105, 218, 0.1)' : '#ffffff',
                cursor: 'pointer',
                textAlign: 'center',
                transition: 'all 0.2s',
              }}
            >
              <Box style={{ marginBottom: '8px', display: 'flex', justifyContent: 'center' }}>
                <SunIcon size={24} />
              </Box>
              <Text style={{ fontSize: '14px', fontWeight: '600' }}>Light</Text>
            </Box>
            <Box
              onClick={() => setTheme('dark')}
              style={{
                padding: '16px',
                border: theme === 'dark' ? '2px solid #0969da' : '2px solid #d0d7de',
                borderRadius: '6px',
                backgroundColor: theme === 'dark' ? 'rgba(9, 105, 218, 0.1)' : '#ffffff',
                cursor: 'pointer',
                textAlign: 'center',
                transition: 'all 0.2s',
              }}
            >
              <Box style={{ marginBottom: '8px', display: 'flex', justifyContent: 'center' }}>
                <MoonIcon size={24} />
              </Box>
              <Text style={{ fontSize: '14px', fontWeight: '600' }}>Dark</Text>
            </Box>
          </Box>
        </Box>
      </Box>

      {/* API Configuration */}
      <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa', marginBottom: '24px' }}>
        <Heading style={{ fontSize: '20px', marginBottom: '16px' }}>API Configuration</Heading>
        
        <Box style={{ display: 'grid', gap: '16px' }}>
          <FormControl>
            <FormControl.Label>API Endpoint</FormControl.Label>
            <TextInput
              type="url"
              value={apiEndpoint}
              onChange={(e) => setApiEndpoint(e.target.value)}
              placeholder="http://localhost:8000"
              style={{ width: '100%' }}
            />
            <FormControl.Caption>The base URL for the MCP Compose API</FormControl.Caption>
          </FormControl>

          <FormControl>
            <FormControl.Label>Auto-refresh Interval</FormControl.Label>
            <Box style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <input
                type="range"
                min="1"
                max="60"
                value={refreshInterval}
                onChange={(e) => setRefreshInterval(Number(e.target.value))}
                style={{ flex: 1 }}
              />
              <Text style={{ fontFamily: 'monospace', fontSize: '14px', minWidth: '64px', textAlign: 'right' }}>
                {refreshInterval}s
              </Text>
            </Box>
            <FormControl.Caption>How often to refresh data from the server</FormControl.Caption>
          </FormControl>
        </Box>
      </Box>

      {/* Notifications */}
      <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa', marginBottom: '24px' }}>
        <Box style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <BellIcon size={20} />
          <Heading style={{ fontSize: '20px' }}>Notifications</Heading>
        </Box>
        
        <Box style={{ display: 'grid', gap: '16px' }}>
          <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', cursor: 'pointer' }}>
            <Box style={{ flex: 1 }}>
              <Text style={{ fontWeight: '600', display: 'block' }}>Enable Notifications</Text>
              <Text style={{ fontSize: '14px', color: '#656d76', display: 'block' }}>
                Show browser notifications for important events
              </Text>
            </Box>
            <Checkbox
              checked={enableNotifications}
              onChange={(e) => setEnableNotifications(e.target.checked)}
            />
          </Box>

          <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', cursor: 'pointer' }}>
            <Box style={{ flex: 1 }}>
              <Text style={{ fontWeight: '600', display: 'block' }}>Enable Sounds</Text>
              <Text style={{ fontSize: '14px', color: '#656d76', display: 'block' }}>
                Play sound alerts for errors and warnings
              </Text>
            </Box>
            <Checkbox
              checked={enableSounds}
              onChange={(e) => setEnableSounds(e.target.checked)}
            />
          </Box>
        </Box>
      </Box>

      {/* Logs Configuration */}
      <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa', marginBottom: '24px' }}>
        <Heading style={{ fontSize: '20px', marginBottom: '16px' }}>Logs</Heading>
        
        <FormControl>
          <FormControl.Label>Maximum Log Lines</FormControl.Label>
          <Select
            value={String(maxLogLines)}
            onChange={(e) => setMaxLogLines(Number(e.target.value))}
            style={{ width: '100%' }}
          >
            <Select.Option value="100">100 lines</Select.Option>
            <Select.Option value="500">500 lines</Select.Option>
            <Select.Option value="1000">1,000 lines</Select.Option>
            <Select.Option value="5000">5,000 lines</Select.Option>
            <Select.Option value="10000">10,000 lines</Select.Option>
          </Select>
          <FormControl.Caption>Maximum number of log lines to keep in memory</FormControl.Caption>
        </FormControl>
      </Box>

      {/* Advanced */}
      <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa', marginBottom: '24px' }}>
        <Heading style={{ fontSize: '20px', marginBottom: '16px' }}>Advanced</Heading>
        
        <Box>
          <Button
            onClick={() => {
              if (confirm('This will clear all cached data. Continue?')) {
                localStorage.clear()
                window.location.reload()
              }
            }}
          >
            Clear Cache & Reload
          </Button>
          <Text style={{ fontSize: '12px', color: '#656d76', display: 'block', marginTop: '8px' }}>
            Clear all cached data and reload the application
          </Text>
        </Box>
      </Box>

      {/* Save Button */}
      <Box style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
        {saved && (
          <Box style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#1a7f37' }}>
            <CheckIcon size={20} />
            <Text>Settings saved!</Text>
          </Box>
        )}
        <Button onClick={handleSave} variant="primary">
          Save Settings
        </Button>
      </Box>

      {/* About */}
      <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa' }}>
        <Heading style={{ fontSize: '20px', marginBottom: '16px' }}>About</Heading>
        <Box style={{ display: 'grid', gap: '8px', fontSize: '14px' }}>
          <Box style={{ display: 'flex', justifyContent: 'space-between' }}>
            <Text style={{ color: '#656d76' }}>Application</Text>
            <Text style={{ fontFamily: 'monospace' }}>MCP Compose</Text>
          </Box>
          <Box style={{ display: 'flex', justifyContent: 'space-between' }}>
            <Text style={{ color: '#656d76' }}>Version</Text>
            <Text style={{ fontFamily: 'monospace' }}>1.0.0</Text>
          </Box>
          <Box style={{ display: 'flex', justifyContent: 'space-between' }}>
            <Text style={{ color: '#656d76' }}>License</Text>
            <Text style={{ fontFamily: 'monospace' }}>MIT</Text>
          </Box>
          <Box style={{ display: 'flex', justifyContent: 'space-between' }}>
            <Text style={{ color: '#656d76' }}>Documentation</Text>
            <Link href="https://github.com/datalayer/mcp-compose">View on GitHub</Link>
          </Box>
        </Box>
      </Box>
    </Box>
  )
}
