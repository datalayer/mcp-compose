/*
 * Copyright (c) 2025-2026 Datalayer, Inc.
 * Distributed under the terms of the Modified BSD License.
 */

import { useQuery, useMutation } from '@tanstack/react-query'
import api from '../api/client'
import { SearchIcon, ToolsIcon, PlayIcon, ChevronRightIcon, AlertIcon } from '@primer/octicons-react'
import { useState } from 'react'
import { Box, Heading, Text, Button, TextInput, Spinner, Select, FormControl } from '@primer/react'

interface Tool {
  name: string
  description?: string
  server_name: string
  input_schema?: {
    type: string
    properties?: Record<string, any>
    required?: string[]
  }
}

export default function Tools() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedServer, setSelectedServer] = useState<string>('')
  const [selectedTool, setSelectedTool] = useState<Tool | null>(null)
  const [toolArgs, setToolArgs] = useState<Record<string, string>>({})
  const [page, setPage] = useState(1)
  const pageSize = 20

  // Fetch tools
  const { data: toolsData, isLoading } = useQuery({
    queryKey: ['tools', selectedServer, page],
    queryFn: () => api.listTools({ 
      server_id: selectedServer || undefined,
      offset: (page - 1) * pageSize,
      limit: pageSize,
    }).then(res => res.data),
  })

  // Fetch servers for filter
  const { data: serversData } = useQuery({
    queryKey: ['servers'],
    queryFn: () => api.listServers().then(res => res.data),
  })

  // Invoke tool mutation
  const invokeMutation = useMutation({
    mutationFn: ({ name, arguments: args }: { name: string, arguments: Record<string, any> }) =>
      api.invokeTool(name, args),
  })

  const tools: Tool[] = toolsData?.tools || []
  const servers = serversData?.servers || []

  // Filter tools by search query
  const filteredTools = tools.filter(tool =>
    tool.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    tool.description?.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const handleInvokeTool = () => {
    if (!selectedTool) return

    // Parse arguments
    const parsedArgs: Record<string, any> = {}
    for (const [key, value] of Object.entries(toolArgs)) {
      try {
        parsedArgs[key] = JSON.parse(value)
      } catch {
        parsedArgs[key] = value
      }
    }

    invokeMutation.mutate({ name: selectedTool.name, arguments: parsedArgs })
  }

  const getRequiredFields = (tool: Tool): string[] => {
    return tool.input_schema?.required || []
  }

  const getProperties = (tool: Tool): Record<string, any> => {
    return tool.input_schema?.properties || {}
  }

  return (
    <Box>
      {/* Header */}
      <Box style={{ marginBottom: '24px' }}>
        <Heading style={{ fontSize: '32px', marginBottom: '8px' }}>Tools</Heading>
        <Text style={{ color: '#656d76' }}>Browse and invoke MCP tools</Text>
      </Box>

      {/* Filters */}
      <Box style={{ display: 'flex', gap: '16px', marginBottom: '24px' }}>
        {/* Search */}
        <Box style={{ flex: 1 }}>
          <TextInput
            leadingVisual={SearchIcon}
            placeholder="Search tools..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: '100%' }}
          />
        </Box>

        {/* Server Filter */}
        <Select
          value={selectedServer}
          onChange={(e) => {
            setSelectedServer(e.target.value)
            setPage(1)
          }}
        >
          <Select.Option value="">All Servers</Select.Option>
          {servers.map((server: any) => (
            <Select.Option key={server.id} value={server.name}>
              {server.name}
            </Select.Option>
          ))}
        </Select>
      </Box>

      {/* Loading State */}
      {isLoading && (
        <Box style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '48px' }}>
          <Spinner size="large" />
        </Box>
      )}

      {/* Tools Grid */}
      {!isLoading && (
        <Box style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '24px' }}>
          {/* Tools List */}
          <Box>
            <Heading style={{ fontSize: '18px', marginBottom: '12px' }}>
              Available Tools ({filteredTools.length})
            </Heading>
            
            {filteredTools.length === 0 && (
              <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa', textAlign: 'center' }}>
                <Text style={{ color: '#656d76' }}>No tools found</Text>
              </Box>
            )}

            <Box style={{ display: 'grid', gap: '8px' }}>
              {filteredTools.map((tool) => (
                <Box
                  key={tool.name}
                  onClick={() => {
                    setSelectedTool(tool)
                    setToolArgs({})
                    invokeMutation.reset()
                  }}
                  style={{
                    padding: '16px',
                    border: selectedTool?.name === tool.name ? '2px solid #0969da' : '1px solid #d0d7de',
                    borderRadius: '6px',
                    backgroundColor: selectedTool?.name === tool.name ? 'rgba(9, 105, 218, 0.1)' : '#f6f8fa',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                  }}
                >
                  <Box style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                    <Box style={{ flex: 1 }}>
                      <Box style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <ToolsIcon size={16} />
                        <Text style={{ fontWeight: '600' }}>{tool.name}</Text>
                      </Box>
                      {tool.description && (
                        <Text style={{ fontSize: '14px', color: '#656d76', marginTop: '4px', display: 'block' }}>
                          {tool.description}
                        </Text>
                      )}
                      <Text style={{ fontSize: '12px', color: '#656d76', marginTop: '4px', display: 'block' }}>
                        Server: {tool.server_name}
                      </Text>
                    </Box>
                    <ChevronRightIcon size={20} />
                  </Box>
                </Box>
              ))}
            </Box>

            {/* Pagination */}
            {toolsData && toolsData.total > pageSize && (
              <Box style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '16px' }}>
                <Button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  size="small"
                >
                  Previous
                </Button>
                <Text style={{ fontSize: '14px', color: '#656d76' }}>
                  Page {page} of {Math.ceil(toolsData.total / pageSize)}
                </Text>
                <Button
                  onClick={() => setPage(p => p + 1)}
                  disabled={page >= Math.ceil(toolsData.total / pageSize)}
                  size="small"
                >
                  Next
                </Button>
              </Box>
            )}
          </Box>

          {/* Tool Details & Invocation */}
          <Box>
            <Heading style={{ fontSize: '18px', marginBottom: '12px' }}>Tool Details</Heading>
            
            {!selectedTool && (
              <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa', textAlign: 'center' }}>
                <Text style={{ color: '#656d76' }}>Select a tool to view details and invoke</Text>
              </Box>
            )}

            {selectedTool && (
              <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa' }}>
                <Box style={{ marginBottom: '16px' }}>
                  <Heading style={{ fontSize: '18px', marginBottom: '8px' }}>{selectedTool.name}</Heading>
                  {selectedTool.description && (
                    <Text style={{ fontSize: '14px', color: '#656d76', marginTop: '8px', display: 'block' }}>
                      {selectedTool.description}
                    </Text>
                  )}
                  <Text style={{ fontSize: '12px', color: '#656d76', marginTop: '8px', display: 'block' }}>
                    Server: {selectedTool.server_name}
                  </Text>
                </Box>

                {/* Input Schema */}
                {Object.keys(getProperties(selectedTool)).length > 0 && (
                  <Box style={{ marginBottom: '16px' }}>
                    <Text style={{ fontSize: '14px', fontWeight: '600', marginBottom: '8px', display: 'block' }}>
                      Parameters
                    </Text>
                    <Box style={{ display: 'grid', gap: '12px' }}>
                      {Object.entries(getProperties(selectedTool)).map(([key, schema]: [string, any]) => (
                        <FormControl key={key}>
                          <FormControl.Label>
                            {key}
                            {getRequiredFields(selectedTool).includes(key) && (
                              <Text as="span" style={{ color: '#cf222e', marginLeft: '4px' }}>*</Text>
                            )}
                          </FormControl.Label>
                          <TextInput
                            value={toolArgs[key] || ''}
                            onChange={(e) => setToolArgs({ ...toolArgs, [key]: e.target.value })}
                            placeholder={schema.description || `Enter ${key}`}
                            style={{ width: '100%' }}
                          />
                          {schema.description && (
                            <FormControl.Caption>{schema.description}</FormControl.Caption>
                          )}
                        </FormControl>
                      ))}
                    </Box>
                  </Box>
                )}

                {/* Invoke Button */}
                <Button
                  onClick={handleInvokeTool}
                  disabled={invokeMutation.isPending}
                  variant="primary"
                  leadingVisual={PlayIcon}
                  style={{ width: '100%', marginBottom: '16px' }}
                >
                  {invokeMutation.isPending ? 'Invoking...' : 'Invoke Tool'}
                </Button>

                {/* Result */}
                {invokeMutation.isError && (
                  <Box style={{ padding: '16px', backgroundColor: 'rgba(207, 34, 46, 0.1)', border: '1px solid #cf222e', borderRadius: '6px' }}>
                    <Box style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                      <AlertIcon size={20} />
                      <Box>
                        <Text style={{ fontWeight: '600', color: '#cf222e', display: 'block' }}>Error</Text>
                        <Text style={{ fontSize: '14px', color: '#cf222e', marginTop: '4px', display: 'block' }}>
                          {(invokeMutation.error as any)?.response?.data?.message || 'Failed to invoke tool'}
                        </Text>
                      </Box>
                    </Box>
                  </Box>
                )}

                {invokeMutation.isSuccess && (
                  <Box style={{ padding: '16px', backgroundColor: 'rgba(26, 127, 55, 0.1)', border: '1px solid #1a7f37', borderRadius: '6px' }}>
                    <Text style={{ fontWeight: '600', color: '#1a7f37', marginBottom: '8px', display: 'block' }}>Result</Text>
                    <Box
                      as="pre"
                      style={{
                        fontSize: '12px',
                        color: '#1a7f37',
                        overflow: 'auto',
                        backgroundColor: '#ffffff',
                        padding: '12px',
                        borderRadius: '6px',
                        fontFamily: 'monospace',
                      }}
                    >
                      {JSON.stringify(invokeMutation.data?.data, null, 2)}
                    </Box>
                  </Box>
                )}
              </Box>
            )}
          </Box>
        </Box>
      )}
    </Box>
  )
}
