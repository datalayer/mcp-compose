/*
 * Copyright (c) 2023-2025 Datalayer, Inc.
 * Distributed under the terms of the Modified BSD License.
 */

import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { 
  Heading, 
  Text, 
  Button,
  Box,
} from '@primer/react'
import {
  ServerIcon,
  ToolsIcon,
  CheckCircleIcon,
  GraphIcon,
  AlertIcon,
} from '@primer/octicons-react'
import { api } from '../api/client'

// NOTE: This file demonstrates Primer React migration patterns using proper CSS properties

export default function Dashboard() {
  const navigate = useNavigate()

  const { data: status } = useQuery({
    queryKey: ['status'],
    queryFn: () => api.getStatus().then(res => res.data),
    refetchInterval: 5000,
  })

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.getHealth().then(res => res.data),
    refetchInterval: 5000,
  })

  const { data: composition } = useQuery({
    queryKey: ['composition'],
    queryFn: () => api.getComposition().then(res => res.data),
    refetchInterval: 10000,
  })

  const { data: metrics } = useQuery({
    queryKey: ['metrics'],
    queryFn: () => api.getMetrics().then(res => res.data),
    refetchInterval: 10000,
  })

  const isHealthy = health?.status === 'healthy'

  return (
    <Box>
      {/* Header */}
      <Box style={{ marginBottom: '32px' }}>
        <Heading style={{ fontSize: '32px', marginBottom: '16px' }}>Dashboard</Heading>
        <Text style={{ color: '#656d76' }}>
          Overview of your MCP Compose
        </Text>
      </Box>

      {/* Stats Grid */}
      <Box
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: '24px',
          marginBottom: '32px',
        }}
      >
        {/* Active Servers */}
        <Box
          style={{
            backgroundColor: '#f6f8fa',
            border: '1px solid #d0d7de',
            borderRadius: '6px',
            padding: '24px',
            transition: 'box-shadow 0.2s',
          }}
        >
          <Box style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Box>
              <Text style={{ fontSize: '12px', color: '#656d76', display: 'block', marginBottom: '8px' }}>
                Active Servers
              </Text>
              <Heading style={{ fontSize: '24px' }}>
                {status?.servers_running || 0}
                <Text style={{ fontSize: '16px', color: '#656d76', marginLeft: '8px' }}>
                  / {status?.servers_total || 0}
                </Text>
              </Heading>
            </Box>
            <Box
              style={{
                backgroundColor: '#ddf4ff',
                padding: '8px',
                borderRadius: '50%',
              }}
            >
              <ServerIcon size={24} />
            </Box>
          </Box>
        </Box>

        {/* Total Tools */}
        <Box
          style={{
            backgroundColor: '#f6f8fa',
            border: '1px solid #d0d7de',
            borderRadius: '6px',
            padding: '24px',
            transition: 'box-shadow 0.2s',
          }}
        >
          <Box style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Box>
              <Text style={{ fontSize: '12px', color: '#656d76', display: 'block', marginBottom: '8px' }}>
                Total Tools
              </Text>
              <Heading style={{ fontSize: '24px' }}>
                {status?.total_tools || 0}
              </Heading>
            </Box>
            <Box
              style={{
                backgroundColor: '#dafbe1',
                padding: '8px',
                borderRadius: '50%',
              }}
            >
              <ToolsIcon size={24} />
            </Box>
          </Box>
        </Box>

        {/* System Health */}
        <Box
          style={{
            backgroundColor: '#f6f8fa',
            border: '1px solid #d0d7de',
            borderRadius: '6px',
            padding: '24px',
            transition: 'box-shadow 0.2s',
          }}
        >
          <Box style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Box>
              <Text style={{ fontSize: '12px', color: '#656d76', display: 'block', marginBottom: '8px' }}>
                System Health
              </Text>
              <Heading style={{ fontSize: '24px', textTransform: 'capitalize' }}>
                {health?.status || 'unknown'}
              </Heading>
            </Box>
            <Box
              style={{
                backgroundColor: isHealthy ? '#dafbe1' : '#ffebe9',
                padding: '8px',
                borderRadius: '50%',
              }}
            >
              {isHealthy ? <CheckCircleIcon size={24} /> : <AlertIcon size={24} />}
            </Box>
          </Box>
        </Box>

        {/* API Requests */}
        <Box
          style={{
            backgroundColor: '#f6f8fa',
            border: '1px solid #d0d7de',
            borderRadius: '6px',
            padding: '24px',
            transition: 'box-shadow 0.2s',
          }}
        >
          <Box style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Box>
              <Text style={{ fontSize: '12px', color: '#656d76', display: 'block', marginBottom: '8px' }}>
                API Requests
              </Text>
              <Heading style={{ fontSize: '24px' }}>
                {metrics?.http_requests_total || 0}
              </Heading>
            </Box>
            <Box
              style={{
                backgroundColor: '#ddf4ff',
                padding: '8px',
                borderRadius: '50%',
              }}
            >
              <GraphIcon size={24} />
            </Box>
          </Box>
        </Box>
      </Box>

      {/* Info and Actions Grid */}
      <Box
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '24px',
        }}
      >
        {/* System Information */}
        <Box
          style={{
            backgroundColor: '#f6f8fa',
            border: '1px solid #d0d7de',
            borderRadius: '6px',
            padding: '24px',
          }}
        >
          <Heading style={{ fontSize: '16px', marginBottom: '16px' }}>System Information</Heading>
          <Box style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text style={{ fontSize: '14px', color: '#656d76' }}>Version</Text>
              <Text style={{ fontSize: '14px', fontWeight: '600' }}>{status?.version || 'N/A'}</Text>
            </Box>
            <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text style={{ fontSize: '14px', color: '#656d76' }}>Uptime</Text>
              <Text style={{ fontSize: '14px', fontWeight: '600' }}>{status?.uptime || 'N/A'}</Text>
            </Box>
            <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text style={{ fontSize: '14px', color: '#656d76' }}>Platform</Text>
              <Text style={{ fontSize: '14px', fontWeight: '600' }}>{status?.platform || 'N/A'}</Text>
            </Box>
            <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text style={{ fontSize: '14px', color: '#656d76' }}>Total Prompts</Text>
              <Text style={{ fontSize: '14px', fontWeight: '600' }}>{status?.total_prompts || 0}</Text>
            </Box>
            <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text style={{ fontSize: '14px', color: '#656d76' }}>Total Resources</Text>
              <Text style={{ fontSize: '14px', fontWeight: '600' }}>{status?.total_resources || 0}</Text>
            </Box>
          </Box>
        </Box>

        {/* Quick Actions */}
        <Box
          style={{
            backgroundColor: '#f6f8fa',
            border: '1px solid #d0d7de',
            borderRadius: '6px',
            padding: '24px',
          }}
        >
          <Heading style={{ fontSize: '16px', marginBottom: '16px' }}>Quick Actions</Heading>
          <Box style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <Button
              onClick={() => navigate('/servers')}
              block
              style={{ justifyContent: 'space-between' }}
            >
              View All Servers
              <Text>→</Text>
            </Button>
            <Button
              onClick={() => navigate('/tools')}
              block
              style={{ justifyContent: 'space-between' }}
            >
              Browse Tools
              <Text>→</Text>
            </Button>
            <Button
              onClick={() => navigate('/configuration')}
              block
              style={{ justifyContent: 'space-between' }}
            >
              Edit Configuration
              <Text>→</Text>
            </Button>
            <Button
              onClick={() => navigate('/logs')}
              block
              style={{ justifyContent: 'space-between' }}
            >
              View Logs
              <Text>→</Text>
            </Button>
          </Box>
        </Box>
      </Box>

      {/* Server Status List */}
      {composition?.servers && composition.servers.length > 0 && (
        <Box style={{ marginTop: '32px' }}>
          <Heading style={{ fontSize: '16px', marginBottom: '16px' }}>Server Status</Heading>
          <Box
            style={{
              backgroundColor: '#f6f8fa',
              border: '1px solid #d0d7de',
              borderRadius: '6px',
              overflow: 'hidden',
            }}
          >
            {composition.servers.map((server: any, index: number) => (
              <Box
                key={server.name}
                style={{
                  padding: '16px',
                  borderBottom: index < composition.servers.length - 1 ? '1px solid #d0d7de' : 'none',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <Box style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <ServerIcon size={20} />
                  <Box>
                    <Text style={{ fontWeight: '600', display: 'block' }}>
                      {server.name}
                    </Text>
                    <Text style={{ fontSize: '12px', color: '#656d76' }}>
                      {server.type} • {server.tools_count || 0} tools
                    </Text>
                  </Box>
                </Box>
                <Box
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    paddingLeft: '8px',
                    paddingRight: '8px',
                    paddingTop: '4px',
                    paddingBottom: '4px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    backgroundColor: server.status === 'running' ? '#dafbe1' : '#ffebe9',
                    color: server.status === 'running' ? '#1a7f37' : '#d1242f',
                  }}
                >
                  {server.status === 'running' ? <CheckCircleIcon size={12} /> : <AlertIcon size={12} />}
                  {server.status}
                </Box>
              </Box>
            ))}
          </Box>
        </Box>
      )}
    </Box>
  )
}
