/*
 * Copyright (c) 2025-2026 Datalayer, Inc.
 * Distributed under the terms of the Modified BSD License.
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { PlayIcon, StopIcon, SyncIcon, TrashIcon, PlusIcon, CheckCircleIcon, AlertIcon, XCircleIcon } from '@primer/octicons-react'
import { Box, Heading, Text, Button, Spinner, Dialog } from '@primer/react'

interface Server {
  id: string
  name: string
  command: string
  args: string[]
  env: Record<string, string>
  transport: string
  state: string
  pid?: number
  uptime?: number
  restart_count?: number
}

export default function Servers() {
  const queryClient = useQueryClient()
  const [selectedServer, setSelectedServer] = useState<string | null>(null)
  const [showAddDialog, setShowAddDialog] = useState(false)

  const { data: serversData, isLoading } = useQuery({
    queryKey: ['servers'],
    queryFn: () => api.listServers().then(res => res.data),
    refetchInterval: 5000,
  })

  const servers: Server[] = serversData?.servers || []

  const startMutation = useMutation({
    mutationFn: (id: string) => api.startServer(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['servers'] })
    },
  })

  const stopMutation = useMutation({
    mutationFn: (id: string) => api.stopServer(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['servers'] })
    },
  })

  const restartMutation = useMutation({
    mutationFn: (id: string) => api.restartServer(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['servers'] })
    },
  })

  const getStatusColor = (state: string) => {
    switch (state?.toLowerCase()) {
      case 'running':
        return '#1a7f37'
      case 'stopped':
        return '#656d76'
      case 'starting':
        return '#0969da'
      case 'stopping':
        return '#9a6700'
      case 'crashed':
        return '#cf222e'
      default:
        return '#656d76'
    }
  }

  const getStatusIcon = (state: string) => {
    switch (state?.toLowerCase()) {
      case 'running':
        return <CheckCircleIcon size={20} />
      case 'crashed':
        return <XCircleIcon size={20} />
      case 'starting':
      case 'stopping':
        return <Spinner size="small" />
      default:
        return <AlertIcon size={20} />
    }
  }

  const formatUptime = (seconds?: number) => {
    if (!seconds) return 'N/A'
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${minutes}m`
  }

  if (isLoading) {
    return (
      <Box style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <Spinner size="large" />
      </Box>
    )
  }

  return (
    <Box>
      {/* Header */}
      <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <Box>
          <Heading style={{ fontSize: '32px', marginBottom: '8px' }}>MCP Servers</Heading>
          <Text style={{ color: '#656d76' }}>Manage your MCP servers</Text>
        </Box>
        <Button onClick={() => setShowAddDialog(true)} leadingVisual={PlusIcon}>
          Add Server
        </Button>
      </Box>

      {/* Empty State */}
      {servers.length === 0 && (
        <Box style={{ padding: '48px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa', textAlign: 'center' }}>
          <Text style={{ color: '#656d76', marginBottom: '16px', display: 'block' }}>
            No servers configured
          </Text>
          <Button onClick={() => setShowAddDialog(true)}>
            Add Your First Server
          </Button>
        </Box>
      )}

      {/* Server List */}
      {servers.length > 0 && (
        <Box style={{ display: 'grid', gap: '16px' }}>
          {servers.map((server) => (
            <Box
              key={server.id}
              onClick={() => setSelectedServer(server.id)}
              style={{
                padding: '24px',
                border: selectedServer === server.id ? '2px solid #0969da' : '1px solid #d0d7de',
                borderRadius: '6px',
                backgroundColor: '#f6f8fa',
                cursor: 'pointer',
                transition: 'border-color 0.2s',
              }}
            >
              <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                {/* Server Info */}
                <Box style={{ flex: 1 }}>
                  <Box style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                    <Box style={{ color: getStatusColor(server.state) }}>
                      {getStatusIcon(server.state)}
                    </Box>
                    <Heading as="h3" style={{ fontSize: '18px' }}>
                      {server.name}
                    </Heading>
                    <Text style={{ fontSize: '14px', fontWeight: '600', color: getStatusColor(server.state) }}>
                      {server.state}
                    </Text>
                  </Box>

                  <Box style={{ display: 'grid', gap: '4px', fontSize: '14px', color: '#656d76' }}>
                    <Box>
                      <Text as="span" style={{ fontWeight: '600' }}>Command:</Text>{' '}
                      <Text
                        as="code"
                        style={{
                          backgroundColor: '#eaeef2',
                          padding: '2px 6px',
                          borderRadius: '3px',
                          fontFamily: 'monospace',
                        }}
                      >
                        {server.command}
                      </Text>
                    </Box>
                    {server.args && server.args.length > 0 && (
                      <Box>
                        <Text as="span" style={{ fontWeight: '600' }}>Args:</Text>{' '}
                        <Text
                          as="code"
                          style={{
                            backgroundColor: '#eaeef2',
                            padding: '2px 6px',
                            borderRadius: '3px',
                            fontFamily: 'monospace',
                          }}
                        >
                          {server.args.join(' ')}
                        </Text>
                      </Box>
                    )}
                    <Box>
                      <Text as="span" style={{ fontWeight: '600' }}>Transport:</Text> {server.transport}
                    </Box>
                    {server.pid && (
                      <Box>
                        <Text as="span" style={{ fontWeight: '600' }}>PID:</Text> {server.pid}
                      </Box>
                    )}
                    {server.uptime !== undefined && (
                      <Box>
                        <Text as="span" style={{ fontWeight: '600' }}>Uptime:</Text> {formatUptime(server.uptime)}
                      </Box>
                    )}
                    {server.restart_count !== undefined && server.restart_count > 0 && (
                      <Box>
                        <Text as="span" style={{ fontWeight: '600' }}>Restarts:</Text> {server.restart_count}
                      </Box>
                    )}
                  </Box>
                </Box>

                {/* Actions */}
                <Box style={{ display: 'flex', gap: '8px' }}>
                  {(server.state === 'stopped' || server.state === 'crashed') && (
                    <Button
                      onClick={(e) => {
                        e.stopPropagation()
                        startMutation.mutate(server.id)
                      }}
                      disabled={startMutation.isPending}
                      size="small"
                      variant="primary"
                      title="Start server"
                    >
                      <PlayIcon size={16} />
                    </Button>
                  )}
                  {server.state === 'running' && (
                    <>
                      <Button
                        onClick={(e) => {
                          e.stopPropagation()
                          restartMutation.mutate(server.id)
                        }}
                        disabled={restartMutation.isPending}
                        size="small"
                        title="Restart server"
                      >
                        <SyncIcon size={16} />
                      </Button>
                      <Button
                        onClick={(e) => {
                          e.stopPropagation()
                          stopMutation.mutate(server.id)
                        }}
                        disabled={stopMutation.isPending}
                        size="small"
                        variant="danger"
                        title="Stop server"
                      >
                        <StopIcon size={16} />
                      </Button>
                    </>
                  )}
                  <Button
                    onClick={(e) => {
                      e.stopPropagation()
                      // TODO: Implement delete
                    }}
                    size="small"
                    title="Delete server"
                  >
                    <TrashIcon size={16} />
                  </Button>
                </Box>
              </Box>
            </Box>
          ))}
        </Box>
      )}

      {/* Add Server Dialog */}
      {showAddDialog && (
        <Dialog
          isOpen={showAddDialog}
          onDismiss={() => setShowAddDialog(false)}
          aria-labelledby="add-server-title"
        >
          <Dialog.Header id="add-server-title">Add Server</Dialog.Header>
          <Box style={{ padding: '16px' }}>
            <Text style={{ color: '#656d76', marginBottom: '16px', display: 'block' }}>
              Server configuration via UI coming in next iteration.
              For now, please add servers via the configuration file.
            </Text>
            <Button onClick={() => setShowAddDialog(false)} variant="primary" style={{ width: '100%' }}>
              Close
            </Button>
          </Box>
        </Dialog>
      )}
    </Box>
  )
}
