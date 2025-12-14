import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { SearchIcon, DownloadIcon, TrashIcon, TerminalIcon, AlertIcon } from '@primer/octicons-react'
import { Box, Heading, Text, Button, TextInput, Select, Checkbox, FormControl } from '@primer/react'

interface LogEntry {
  timestamp: string
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'
  server?: string
  message: string
}

export default function Logs() {
  const [filter, setFilter] = useState<string>('')
  const [levelFilter, setLevelFilter] = useState<string>('ALL')
  const [serverFilter, setServerFilter] = useState<string>('ALL')
  const [autoScroll, setAutoScroll] = useState(true)
  const [maxLines, setMaxLines] = useState<number>(500)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const logsContainerRef = useRef<HTMLDivElement>(null)

  const { data: servers } = useQuery({
    queryKey: ['servers'],
    queryFn: () => api.listServers().then(res => res.data),
  })

  const [logs, setLogs] = useState<LogEntry[]>([
    { timestamp: new Date().toISOString(), level: 'INFO', server: 'filesystem', message: 'Server started successfully' },
    { timestamp: new Date().toISOString(), level: 'INFO', server: 'calculator', message: 'Initializing calculator tools' },
    { timestamp: new Date().toISOString(), level: 'DEBUG', server: 'filesystem', message: 'Loading file system configuration' },
    { timestamp: new Date().toISOString(), level: 'WARNING', server: 'calculator', message: 'Deprecated function called' },
  ])

  useEffect(() => {
    const interval = setInterval(() => {
      const levels: LogEntry['level'][] = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
      const messages = [
        'Processing request',
        'Tool invoked successfully',
        'Configuration updated',
        'Health check passed',
        'Connection established',
        'Cache cleared',
        'Request completed in 45ms',
      ]
      const serverList = servers?.servers?.map((s: any) => s.name) || ['filesystem', 'calculator']
      
      const newLog: LogEntry = {
        timestamp: new Date().toISOString(),
        level: levels[Math.floor(Math.random() * levels.length)],
        server: serverList[Math.floor(Math.random() * serverList.length)],
        message: messages[Math.floor(Math.random() * messages.length)],
      }
      
      setLogs(prev => {
        const updated = [...prev, newLog]
        return updated.slice(-maxLines)
      })
    }, 2000)

    return () => clearInterval(interval)
  }, [servers, maxLines])

  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoScroll])

  const filteredLogs = logs.filter(log => {
    if (filter && !log.message.toLowerCase().includes(filter.toLowerCase())) {
      return false
    }
    if (levelFilter !== 'ALL' && log.level !== levelFilter) {
      return false
    }
    if (serverFilter !== 'ALL' && log.server !== serverFilter) {
      return false
    }
    return true
  })

  const clearLogs = () => {
    setLogs([])
  }

  const downloadLogs = () => {
    const logText = filteredLogs.map(log => 
      `${log.timestamp} [${log.level}] ${log.server ? `[${log.server}] ` : ''}${log.message}`
    ).join('\n')
    
    const blob = new Blob([logText], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `logs-${new Date().toISOString()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const getLevelColor = (level: LogEntry['level']) => {
    switch (level) {
      case 'DEBUG': return '#656d76'
      case 'INFO': return '#0969da'
      case 'WARNING': return '#9a6700'
      case 'ERROR': return '#cf222e'
      case 'CRITICAL': return '#a40e26'
      default: return '#1f2328'
    }
  }

  const getLevelBg = (level: LogEntry['level']) => {
    switch (level) {
      case 'DEBUG': return '#f6f8fa'
      case 'INFO': return '#ddf4ff'
      case 'WARNING': return '#fff8c5'
      case 'ERROR': return '#ffebe9'
      case 'CRITICAL': return '#ffdddb'
      default: return '#f6f8fa'
    }
  }

  return (
    <Box>
      <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <Box>
          <Heading style={{ fontSize: '32px', marginBottom: '8px' }}>Logs</Heading>
          <Text style={{ color: '#656d76' }}>Real-time system and server logs</Text>
        </Box>
        <Box style={{ display: 'flex', gap: '8px' }}>
          <Button onClick={downloadLogs} leadingVisual={DownloadIcon}>
            Download
          </Button>
          <Button onClick={clearLogs} variant="danger" leadingVisual={TrashIcon}>
            Clear
          </Button>
        </Box>
      </Box>

      <Box style={{ padding: '16px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa', marginBottom: '16px' }}>
        <Box style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <Box style={{ flex: '1', minWidth: '200px' }}>
            <TextInput
              leadingVisual={SearchIcon}
              placeholder="Search logs..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              style={{ width: '100%' }}
            />
          </Box>
          
          <FormControl>
            <FormControl.Label visuallyHidden>Level Filter</FormControl.Label>
            <Select
              value={levelFilter}
              onChange={(e) => setLevelFilter(e.target.value)}
            >
              <Select.Option value="ALL">All Levels</Select.Option>
              <Select.Option value="DEBUG">Debug</Select.Option>
              <Select.Option value="INFO">Info</Select.Option>
              <Select.Option value="WARNING">Warning</Select.Option>
              <Select.Option value="ERROR">Error</Select.Option>
              <Select.Option value="CRITICAL">Critical</Select.Option>
            </Select>
          </FormControl>

          <FormControl>
            <FormControl.Label visuallyHidden>Server Filter</FormControl.Label>
            <Select
              value={serverFilter}
              onChange={(e) => setServerFilter(e.target.value)}
            >
              <Select.Option value="ALL">All Servers</Select.Option>
              {servers?.servers?.map((server: any) => (
                <Select.Option key={server.id} value={server.name}>{server.name}</Select.Option>
              ))}
            </Select>
          </FormControl>

          <Box style={{ display: 'flex', alignItems: 'center' }}>
            <Checkbox
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
            />
            <Text style={{ fontSize: '14px', marginLeft: '8px' }}>Auto-scroll</Text>
          </Box>

          <Box style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Text style={{ fontSize: '14px', color: '#656d76' }}>Max lines:</Text>
            <Select
              value={String(maxLines)}
              onChange={(e) => setMaxLines(Number(e.target.value))}
            >
              <Select.Option value="100">100</Select.Option>
              <Select.Option value="500">500</Select.Option>
              <Select.Option value="1000">1000</Select.Option>
              <Select.Option value="5000">5000</Select.Option>
            </Select>
          </Box>
        </Box>
      </Box>

      <Box style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '16px' }}>
        <Box style={{ padding: '16px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa' }}>
          <Text style={{ fontSize: '14px', color: '#656d76', display: 'block' }}>Total Lines</Text>
          <Text style={{ fontSize: '24px', fontWeight: 'bold', display: 'block' }}>{filteredLogs.length}</Text>
        </Box>
        <Box style={{ padding: '16px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa' }}>
          <Text style={{ fontSize: '14px', color: '#656d76', display: 'block' }}>Errors</Text>
          <Text style={{ fontSize: '24px', fontWeight: 'bold', color: '#cf222e', display: 'block' }}>
            {filteredLogs.filter(l => l.level === 'ERROR' || l.level === 'CRITICAL').length}
          </Text>
        </Box>
        <Box style={{ padding: '16px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa' }}>
          <Text style={{ fontSize: '14px', color: '#656d76', display: 'block' }}>Warnings</Text>
          <Text style={{ fontSize: '24px', fontWeight: 'bold', color: '#9a6700', display: 'block' }}>
            {filteredLogs.filter(l => l.level === 'WARNING').length}
          </Text>
        </Box>
        <Box style={{ padding: '16px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa' }}>
          <Text style={{ fontSize: '14px', color: '#656d76', display: 'block' }}>Info</Text>
          <Text style={{ fontSize: '24px', fontWeight: 'bold', color: '#0969da', display: 'block' }}>
            {filteredLogs.filter(l => l.level === 'INFO').length}
          </Text>
        </Box>
      </Box>

      <Box style={{ border: '1px solid #d0d7de', borderRadius: '6px', overflow: 'hidden' }}>
        <Box style={{ padding: '12px 16px', borderBottom: '1px solid #d0d7de', backgroundColor: '#f6f8fa', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TerminalIcon size={16} />
            <Text style={{ fontFamily: 'monospace', fontSize: '14px' }}>Console Output</Text>
          </Box>
          <Text style={{ fontSize: '14px', color: '#656d76' }}>
            {filteredLogs.length} / {logs.length} lines
          </Text>
        </Box>
        
        <Box
          ref={logsContainerRef}
          style={{
            height: '600px',
            overflowY: 'auto',
            backgroundColor: '#f6f8fa',
            padding: '16px',
            fontFamily: 'monospace',
            fontSize: '12px',
          }}
        >
          {filteredLogs.length === 0 ? (
            <Box style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#656d76' }}>
              <Box style={{ marginBottom: '16px' }}>
                <AlertIcon size={48} />
              </Box>
              <Text>No logs to display</Text>
              <Text style={{ fontSize: '12px', marginTop: '8px' }}>Logs will appear here as they are generated</Text>
            </Box>
          ) : (
            filteredLogs.map((log, index) => (
              <Box
                key={index}
                style={{
                  padding: '4px 8px',
                  borderRadius: '3px',
                  marginBottom: '4px',
                  backgroundColor: getLevelBg(log.level),
                }}
              >
                <Text as="span" style={{ color: '#656d76' }}>
                  {new Date(log.timestamp).toLocaleTimeString()}
                </Text>
                {' '}
                <Text as="span" style={{ fontWeight: 'bold', color: getLevelColor(log.level) }}>
                  [{log.level}]
                </Text>
                {log.server && (
                  <>
                    {' '}
                    <Text as="span" style={{ color: '#8250df' }}>[{log.server}]</Text>
                  </>
                )}
                {' '}
                <Text as="span">{log.message}</Text>
              </Box>
            ))
          )}
          <div ref={logsEndRef} />
        </Box>
      </Box>
    </Box>
  )
}
