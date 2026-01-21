/*
 * Copyright (c) 2023-2025 Datalayer, Inc.
 * Distributed under the terms of the Modified BSD License.
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { Box, Heading, Text, Button, TextInput, FormControl, Dialog, Spinner } from '@primer/react'
import { 
  BroadcastIcon, 
  TrashIcon, 
  PlusIcon, 
  CheckIcon, 
  AlertIcon,
  SyncIcon 
} from '@primer/octicons-react'
import DemoBanner from '../components/DemoBanner'

type TranslatorType = 'stdio-to-sse' | 'sse-to-stdio'

interface Translator {
  name: string
  type: TranslatorType
  sse_url?: string
  command?: string
  args?: string[]
  created_at?: string
}

export default function Translators() {
  const queryClient = useQueryClient()
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [translatorType, setTranslatorType] = useState<TranslatorType>('stdio-to-sse')
  
  // STDIO to SSE form
  const [stdioName, setStdioName] = useState('')
  const [sseUrl, setSseUrl] = useState('')
  
  // SSE to STDIO form
  const [sseName, setSseName] = useState('')
  const [command, setCommand] = useState('')
  const [args, setArgs] = useState('')

  // Fetch translators
  const { data: translators, isLoading, error } = useQuery({
    queryKey: ['translators'],
    queryFn: () => api.listTranslators().then(res => res.data),
    refetchInterval: 10000,
  })

  // Create STDIO to SSE mutation
  const createStdioToSseMutation = useMutation({
    mutationFn: (data: { name: string; sse_url: string }) =>
      api.createStdioToSse(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['translators'] })
      resetForm()
    },
  })

  // Create SSE to STDIO mutation
  const createSseToStdioMutation = useMutation({
    mutationFn: (data: { name: string; command: string; args?: string[] }) =>
      api.createSseToStdio(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['translators'] })
      resetForm()
    },
  })

  // Delete translator mutation
  const deleteMutation = useMutation({
    mutationFn: (name: string) => api.deleteTranslator(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['translators'] })
    },
  })

  const resetForm = () => {
    setShowAddDialog(false)
    setStdioName('')
    setSseUrl('')
    setSseName('')
    setCommand('')
    setArgs('')
  }

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    
    if (translatorType === 'stdio-to-sse') {
      if (stdioName.trim() && sseUrl.trim()) {
        createStdioToSseMutation.mutate({
          name: stdioName.trim(),
          sse_url: sseUrl.trim(),
        })
      }
    } else {
      if (sseName.trim() && command.trim()) {
        createSseToStdioMutation.mutate({
          name: sseName.trim(),
          command: command.trim(),
          args: args.trim() ? args.trim().split(' ') : undefined,
        })
      }
    }
  }

  const handleDelete = (name: string) => {
    if (confirm(`Are you sure you want to delete translator "${name}"?`)) {
      deleteMutation.mutate(name)
    }
  }

  if (isLoading) {
    return (
      <Box style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '384px' }}>
        <Spinner size="large" />
      </Box>
    )
  }

  if (error) {
    return (
      <Box style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '384px' }}>
        <Box style={{ textAlign: 'center' }}>
          <Box style={{ color: '#cf222e', marginBottom: '16px' }}>
            <AlertIcon size={48} />
          </Box>
          <Text style={{ color: '#cf222e' }}>Failed to load translators</Text>
        </Box>
      </Box>
    )
  }

  const translatorList = translators?.translators || []

  return (
    <Box>
      <DemoBanner message="Translator management is fully functional. You can add, configure, and monitor protocol translators for your MCP servers." />
      
      {/* Header */}
      <Box style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <Box>
          <Heading style={{ fontSize: '32px', marginBottom: '8px' }}>Translators</Heading>
          <Text style={{ color: '#656d76' }}>
            Manage protocol translators for MCP servers
          </Text>
        </Box>
        <Button 
          variant="primary"
          onClick={() => setShowAddDialog(true)}
          leadingVisual={PlusIcon}
        >
          Add Translator
        </Button>
      </Box>

      {/* Info Banner */}
      <Box
        style={{
          backgroundColor: 'rgba(9, 105, 218, 0.1)',
          border: '1px solid rgba(9, 105, 218, 0.2)',
          borderRadius: '6px',
          padding: '16px',
          marginBottom: '24px',
        }}
      >
        <Box style={{ display: 'flex', gap: '12px' }}>
          <Box style={{ color: '#0969da', marginTop: '2px' }}>
            <BroadcastIcon size={20} />
          </Box>
          <Box>
            <Heading as="h3" style={{ fontSize: '14px', fontWeight: 600, color: '#0969da', marginBottom: '4px' }}>
              About Protocol Translators
            </Heading>
            <Text style={{ fontSize: '13px', color: '#656d76', display: 'block', marginTop: '4px' }}>
              Protocol translators enable communication between different MCP transport protocols:
            </Text>
            <Box as="ul" style={{ fontSize: '13px', color: '#656d76', marginTop: '8px', paddingLeft: '20px' }}>
              <li style={{ marginBottom: '4px' }}>
                <strong>STDIO → SSE:</strong> Exposes STDIO servers via Server-Sent Events for web clients
              </li>
              <li>
                <strong>SSE → STDIO:</strong> Connects to SSE servers using STDIO interface
              </li>
            </Box>
          </Box>
        </Box>
      </Box>

      {/* Translators List */}
      {translatorList.length > 0 ? (
        <Box style={{ display: 'grid', gap: '16px' }}>
          {translatorList.map((translator: Translator) => (
            <Box
              key={translator.name}
              style={{
                border: '1px solid #d0d7de',
                borderRadius: '6px',
                padding: '24px',
              }}
            >
              <Box style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Box style={{ flex: 1 }}>
                  <Box style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Box
                      style={{
                        padding: '8px',
                        backgroundColor: 'rgba(9, 105, 218, 0.1)',
                        borderRadius: '6px',
                      }}
                    >
                      <Box style={{ color: '#0969da' }}>
                        <SyncIcon size={20} />
                      </Box>
                    </Box>
                    <Box>
                      <Heading as="h3" style={{ fontSize: '18px', fontWeight: 600, marginBottom: '4px' }}>
                        {translator.name}
                      </Heading>
                      <Text style={{ fontSize: '13px', color: '#656d76' }}>
                        {translator.type === 'stdio-to-sse' ? 'STDIO → SSE' : 'SSE → STDIO'}
                      </Text>
                    </Box>
                  </Box>

                  <Box style={{ marginTop: '16px' }}>
                    {translator.type === 'stdio-to-sse' && translator.sse_url && (
                      <Box
                        style={{
                          padding: '12px',
                          backgroundColor: '#f6f8fa',
                          borderRadius: '6px',
                        }}
                      >
                        <Text style={{ fontSize: '11px', color: '#656d76', display: 'block' }}>
                          SSE Endpoint
                        </Text>
                        <Text style={{ fontSize: '13px', fontFamily: 'monospace', display: 'block', marginTop: '4px' }}>
                          {translator.sse_url}
                        </Text>
                      </Box>
                    )}
                    {translator.type === 'sse-to-stdio' && translator.command && (
                      <Box
                        style={{
                          padding: '12px',
                          backgroundColor: '#f6f8fa',
                          borderRadius: '6px',
                        }}
                      >
                        <Text style={{ fontSize: '11px', color: '#656d76', display: 'block' }}>
                          Command
                        </Text>
                        <Text style={{ fontSize: '13px', fontFamily: 'monospace', display: 'block', marginTop: '4px' }}>
                          {translator.command}
                          {translator.args && translator.args.length > 0 && ` ${translator.args.join(' ')}`}
                        </Text>
                      </Box>
                    )}
                  </Box>

                  {translator.created_at && (
                    <Box style={{ marginTop: '12px' }}>
                      <Text style={{ fontSize: '11px', color: '#656d76' }}>
                        Created: {new Date(translator.created_at).toLocaleString()}
                      </Text>
                    </Box>
                  )}
                </Box>

                <Button
                  variant="danger"
                  onClick={() => handleDelete(translator.name)}
                  disabled={deleteMutation.isPending}
                  aria-label="Delete translator"
                  style={{ marginLeft: '16px' }}
                >
                  <TrashIcon />
                </Button>
              </Box>
            </Box>
          ))}
        </Box>
      ) : (
        <Box
          style={{
            border: '1px solid #d0d7de',
            borderRadius: '6px',
            padding: '48px',
          }}
        >
          <Box style={{ textAlign: 'center' }}>
            <Box style={{ color: '#656d76', marginBottom: '16px' }}>
              <BroadcastIcon size={64} />
            </Box>
            <Heading as="h3" style={{ fontSize: '18px', marginBottom: '8px' }}>
              No translators configured
            </Heading>
            <Text style={{ color: '#656d76', display: 'block', marginBottom: '24px' }}>
              Create a translator to enable cross-protocol communication
            </Text>
            <Button
              variant="primary"
              onClick={() => setShowAddDialog(true)}
              leadingVisual={PlusIcon}
            >
              Add Your First Translator
            </Button>
          </Box>
        </Box>
      )}

      {/* Add Translator Dialog */}
      {showAddDialog && (
        <Dialog
          isOpen={showAddDialog}
          onDismiss={resetForm}
          aria-labelledby="add-translator-title"
        >
          <Dialog.Header id="add-translator-title">Add Protocol Translator</Dialog.Header>
          <Box as="form" onSubmit={handleCreate} style={{ padding: '16px' }}>
            {/* Translator Type Selection */}
            <FormControl>
              <FormControl.Label>Translator Type</FormControl.Label>
              <Box style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px', marginTop: '12px' }}>
                <Box
                  as="button"
                  type="button"
                  onClick={() => setTranslatorType('stdio-to-sse')}
                  style={{
                    padding: '16px',
                    border: translatorType === 'stdio-to-sse' ? '2px solid #0969da' : '2px solid #d0d7de',
                    borderRadius: '6px',
                    backgroundColor: translatorType === 'stdio-to-sse' ? 'rgba(9, 105, 218, 0.1)' : 'transparent',
                    cursor: 'pointer',
                    textAlign: 'center',
                  }}
                >
                  <Box style={{ color: '#0969da', marginBottom: '8px' }}>
                    <SyncIcon size={24} />
                  </Box>
                  <Box style={{ fontWeight: 600, fontSize: '13px', marginBottom: '4px' }}>
                    STDIO → SSE
                  </Box>
                  <Text style={{ fontSize: '11px', color: '#656d76' }}>
                    Expose STDIO via SSE
                  </Text>
                </Box>
                <Box
                  as="button"
                  type="button"
                  onClick={() => setTranslatorType('sse-to-stdio')}
                  style={{
                    padding: '16px',
                    border: translatorType === 'sse-to-stdio' ? '2px solid #0969da' : '2px solid #d0d7de',
                    borderRadius: '6px',
                    backgroundColor: translatorType === 'sse-to-stdio' ? 'rgba(9, 105, 218, 0.1)' : 'transparent',
                    cursor: 'pointer',
                    textAlign: 'center',
                  }}
                >
                  <Box style={{ color: '#0969da', marginBottom: '8px', transform: 'rotate(180deg)' }}>
                    <SyncIcon size={24} />
                  </Box>
                  <Box style={{ fontWeight: 600, fontSize: '13px', marginBottom: '4px' }}>
                    SSE → STDIO
                  </Box>
                  <Text style={{ fontSize: '11px', color: '#656d76' }}>
                    Connect to SSE via STDIO
                  </Text>
                </Box>
              </Box>
            </FormControl>

            <Box style={{ marginTop: '16px' }}>
              {translatorType === 'stdio-to-sse' ? (
                <>
                  <FormControl required>
                    <FormControl.Label>
                      Translator Name <Text style={{ color: '#cf222e' }}>*</Text>
                    </FormControl.Label>
                    <TextInput
                      value={stdioName}
                      onChange={(e) => setStdioName(e.target.value)}
                      placeholder="my-translator"
                      required
                      block
                    />
                  </FormControl>
                  <Box style={{ marginTop: '16px' }}>
                    <FormControl required>
                    <FormControl.Label>
                      SSE URL <Text style={{ color: '#cf222e' }}>*</Text>
                    </FormControl.Label>
                    <TextInput
                      type="url"
                      value={sseUrl}
                      onChange={(e) => setSseUrl(e.target.value)}
                      placeholder="http://localhost:3001/sse"
                      required
                      block
                    />
                      <FormControl.Caption>
                        The SSE endpoint to expose the STDIO server through
                      </FormControl.Caption>
                    </FormControl>
                  </Box>
                </>
              ) : (
                <>
                  <FormControl required>
                    <FormControl.Label>
                      Translator Name <Text style={{ color: '#cf222e' }}>*</Text>
                    </FormControl.Label>
                    <TextInput
                      value={sseName}
                      onChange={(e) => setSseName(e.target.value)}
                      placeholder="my-translator"
                      required
                      block
                    />
                  </FormControl>
                  <Box style={{ marginTop: '16px' }}>
                    <FormControl required>
                      <FormControl.Label>
                        Command <Text style={{ color: '#cf222e' }}>*</Text>
                      </FormControl.Label>
                    <TextInput
                      value={command}
                      onChange={(e) => setCommand(e.target.value)}
                      placeholder="python -m mcp_server"
                      required
                      block
                    />
                      <FormControl.Caption>
                        The command to launch the STDIO process
                      </FormControl.Caption>
                    </FormControl>
                  </Box>
                  <Box style={{ marginTop: '16px' }}>
                    <FormControl>
                    <FormControl.Label>Arguments (optional)</FormControl.Label>
                    <TextInput
                      value={args}
                      onChange={(e) => setArgs(e.target.value)}
                      placeholder="--port 8080 --debug"
                      block
                    />
                      <FormControl.Caption>
                        Space-separated command arguments
                      </FormControl.Caption>
                    </FormControl>
                  </Box>
                </>
              )}
            </Box>

            {(createStdioToSseMutation.isError || createSseToStdioMutation.isError) && (
              <Box
                style={{
                  padding: '12px',
                  backgroundColor: 'rgba(207, 34, 46, 0.1)',
                  border: '1px solid rgba(207, 34, 46, 0.2)',
                  borderRadius: '6px',
                  marginTop: '16px',
                }}
              >
                <Text style={{ fontSize: '13px', color: '#cf222e' }}>
                  Failed to create translator. Please check your inputs and try again.
                </Text>
              </Box>
            )}

            <Box style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '24px' }}>
              <Button type="button" onClick={resetForm}>
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                disabled={createStdioToSseMutation.isPending || createSseToStdioMutation.isPending}
              >
                {(createStdioToSseMutation.isPending || createSseToStdioMutation.isPending) ? (
                  <>
                    <Box style={{ display: 'inline-block', marginRight: '8px' }}>
                      <Spinner size="small" />
                    </Box>
                    Creating...
                  </>
                ) : (
                  'Create'
                )}
              </Button>
            </Box>
          </Box>
        </Dialog>
      )}

      {/* Success Toast */}
      {(createStdioToSseMutation.isSuccess || createSseToStdioMutation.isSuccess) && (
        <Box
          style={{
            position: 'fixed',
            bottom: '16px',
            right: '16px',
            backgroundColor: '#1a7f37',
            color: 'white',
            padding: '12px 16px',
            borderRadius: '6px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <CheckIcon size={20} />
          <Text style={{ color: 'white' }}>Translator created successfully!</Text>
        </Box>
      )}
    </Box>
  )
}
