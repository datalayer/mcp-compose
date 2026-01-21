/*
 * Copyright (c) 2023-2025 Datalayer, Inc.
 * Distributed under the terms of the Modified BSD License.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { SyncIcon, CheckCircleIcon, AlertIcon } from '@primer/octicons-react'
import { Box, Heading, Text, Button, Flash, Spinner } from '@primer/react'

export default function Configuration() {
  const queryClient = useQueryClient()

  const { data: configData, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: () => api.getConfig().then(res => res.data),
  })

  const config = configData ? JSON.stringify(configData, null, 2) : ''

  const reloadMutation = useMutation({
    mutationFn: () => api.reloadConfig(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] })
      queryClient.invalidateQueries({ queryKey: ['servers'] })
    },
  })

  const handleReload = () => {
    if (confirm('Reload configuration from mcp_compose.toml? This will restart all servers.')) {
      reloadMutation.mutate()
    }
  }

  return (
    <Box>
      <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <Box>
          <Heading style={{ fontSize: '32px', marginBottom: '8px' }}>Configuration</Heading>
          <Text style={{ color: '#656d76' }}>View current runtime configuration</Text>
        </Box>
        
        <Box style={{ display: 'flex', gap: '8px' }}>
          <Button
            onClick={handleReload}
            disabled={reloadMutation.isPending}
            leadingVisual={SyncIcon}
          >
            Reload from mcp_compose.toml
          </Button>
        </Box>
      </Box>

      {reloadMutation.isSuccess && (
        <Flash variant="success" style={{ marginBottom: '16px' }}>
          <Box style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircleIcon size={16} />
            <Text>Configuration reloaded from mcp_compose.toml</Text>
          </Box>
        </Flash>
      )}

      {reloadMutation.isError && (
        <Flash variant="danger" style={{ marginBottom: '16px' }}>
          <Box style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
            <AlertIcon size={20} />
            <Box>
              <Text style={{ fontWeight: 'bold', display: 'block' }}>Reload Error</Text>
              <Text style={{ fontSize: '14px', marginTop: '4px', display: 'block' }}>
                {(reloadMutation.error as any)?.response?.data?.message || 'Failed to reload configuration'}
              </Text>
            </Box>
          </Box>
        </Flash>
      )}

      <Box
        style={{
          border: '1px solid #d0d7de',
          borderRadius: '6px',
          overflow: 'hidden',
          backgroundColor: '#f6f8fa',
        }}
      >
        {isLoading ? (
          <Box style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '48px' }}>
            <Spinner size="large" />
          </Box>
        ) : (
          <Box>
            <Box
              style={{
                padding: '12px 16px',
                borderBottom: '1px solid #d0d7de',
                backgroundColor: '#f6f8fa',
              }}
            >
              <Text style={{ fontSize: '14px', fontWeight: 'bold', display: 'block' }}>
                Runtime Configuration (Read-Only)
              </Text>
              <Text style={{ fontSize: '12px', color: '#656d76', marginTop: '4px', display: 'block' }}>
                This is the current parsed configuration. To edit, modify mcp_compose.toml and reload.
              </Text>
            </Box>
            <Box
              as="pre"
              style={{
                width: '100%',
                height: '600px',
                padding: '16px',
                fontFamily: 'monospace',
                fontSize: '14px',
                border: 'none',
                margin: 0,
                overflow: 'auto',
                backgroundColor: '#ffffff',
              }}
            >
              {config || 'Loading configuration...'}
            </Box>
          </Box>
        )}
      </Box>

      <Box
        style={{
          padding: '16px',
          border: '1px solid #d0d7de',
          borderRadius: '6px',
          backgroundColor: '#f6f8fa',
          marginTop: '16px',
        }}
      >
        <Heading as="h3" style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '8px' }}>
          Configuration Guide
        </Heading>
        <Box as="ul" style={{ fontSize: '14px', color: '#656d76', listStyle: 'disc', paddingLeft: '20px' }}>
          <li>Configuration is stored in <code style={{ backgroundColor: '#ffffff', padding: '2px 4px', borderRadius: '3px' }}>mcp_compose.toml</code> file</li>
          <li>This view shows the current runtime configuration in JSON format (read-only)</li>
          <li>To edit configuration, modify the <code style={{ backgroundColor: '#ffffff', padding: '2px 4px', borderRadius: '3px' }}>mcp_compose.toml</code> file directly</li>
          <li>Click "Reload from mcp_compose.toml" to apply changes from the file</li>
          <li>Changes to server configuration will restart affected servers</li>
        </Box>
      </Box>
    </Box>
  )
}
