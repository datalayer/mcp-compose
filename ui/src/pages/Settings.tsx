import { useState } from 'react'
import { useThemeStore } from '../store/theme'
import { Moon, Sun, Bell, Save, CheckCircle } from 'lucide-react'

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
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-foreground">Settings</h1>
        <p className="mt-2 text-muted-foreground">
          Configure application preferences and behavior
        </p>
      </div>

      {/* Appearance */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">Appearance</h2>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-3">Theme</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => setTheme('light')}
                className={`p-4 border-2 rounded-lg transition-all ${
                  theme === 'light'
                    ? 'border-primary bg-primary/10'
                    : 'border-border hover:border-primary/50'
                }`}
              >
                <Sun className="h-6 w-6 mx-auto mb-2" />
                <div className="text-sm font-medium">Light</div>
              </button>
              <button
                onClick={() => setTheme('dark')}
                className={`p-4 border-2 rounded-lg transition-all ${
                  theme === 'dark'
                    ? 'border-primary bg-primary/10'
                    : 'border-border hover:border-primary/50'
                }`}
              >
                <Moon className="h-6 w-6 mx-auto mb-2" />
                <div className="text-sm font-medium">Dark</div>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* API Configuration */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">API Configuration</h2>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              API Endpoint
            </label>
            <input
              type="url"
              value={apiEndpoint}
              onChange={(e) => setApiEndpoint(e.target.value)}
              className="w-full px-3 py-2 bg-background border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="http://localhost:8000"
            />
            <p className="text-xs text-muted-foreground mt-2">
              The base URL for the MCP Compose API
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Auto-refresh Interval
            </label>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min="1"
                max="60"
                value={refreshInterval}
                onChange={(e) => setRefreshInterval(Number(e.target.value))}
                className="flex-1"
              />
              <span className="text-sm font-mono w-16 text-right">{refreshInterval}s</span>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              How often to refresh data from the server
            </p>
          </div>
        </div>
      </div>

      {/* Notifications */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
          <Bell className="h-5 w-5" />
          Notifications
        </h2>
        
        <div className="space-y-4">
          <label className="flex items-center justify-between cursor-pointer">
            <div>
              <div className="font-medium">Enable Notifications</div>
              <div className="text-sm text-muted-foreground">
                Show browser notifications for important events
              </div>
            </div>
            <input
              type="checkbox"
              checked={enableNotifications}
              onChange={(e) => setEnableNotifications(e.target.checked)}
              className="w-5 h-5 rounded border-input"
            />
          </label>

          <label className="flex items-center justify-between cursor-pointer">
            <div>
              <div className="font-medium">Enable Sounds</div>
              <div className="text-sm text-muted-foreground">
                Play sound alerts for errors and warnings
              </div>
            </div>
            <input
              type="checkbox"
              checked={enableSounds}
              onChange={(e) => setEnableSounds(e.target.checked)}
              className="w-5 h-5 rounded border-input"
            />
          </label>
        </div>
      </div>

      {/* Logs Configuration */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">Logs</h2>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Maximum Log Lines
            </label>
            <select
              value={maxLogLines}
              onChange={(e) => setMaxLogLines(Number(e.target.value))}
              className="w-full px-3 py-2 bg-background border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value={100}>100 lines</option>
              <option value={500}>500 lines</option>
              <option value={1000}>1,000 lines</option>
              <option value={5000}>5,000 lines</option>
              <option value={10000}>10,000 lines</option>
            </select>
            <p className="text-xs text-muted-foreground mt-2">
              Maximum number of log lines to keep in memory
            </p>
          </div>
        </div>
      </div>

      {/* Advanced */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">Advanced</h2>
        
        <div className="space-y-4">
          <button
            className="px-4 py-2 bg-muted text-foreground rounded-md hover:bg-muted/80 transition-colors"
            onClick={() => {
              if (confirm('This will clear all cached data. Continue?')) {
                localStorage.clear()
                window.location.reload()
              }
            }}
          >
            Clear Cache & Reload
          </button>
          <p className="text-xs text-muted-foreground">
            Clear all cached data and reload the application
          </p>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end gap-3">
        {saved && (
          <div className="flex items-center gap-2 text-green-500 animate-in fade-in">
            <CheckCircle className="h-5 w-5" />
            <span>Settings saved!</span>
          </div>
        )}
        <button
          onClick={handleSave}
          className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors flex items-center gap-2"
        >
          <Save className="h-4 w-4" />
          Save Settings
        </button>
      </div>

      {/* About */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">About</h2>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Application</span>
            <span className="font-mono">MCP Compose</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Version</span>
            <span className="font-mono">1.0.0</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">License</span>
            <span className="font-mono">MIT</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Documentation</span>
            <a href="https://github.com/datalayer/mcp-compose" className="text-primary hover:underline">
              View on GitHub
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
