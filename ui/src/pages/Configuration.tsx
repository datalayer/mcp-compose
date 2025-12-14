import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { CheckIcon, SyncIcon, CheckCircleIcon, AlertIcon, FileCodeIcon } from '@primer/octicons-react'
import { useState, useEffect } from 'react'
import { Box, Heading, Text, Button, Textarea, Flash, Spinner } from '@primer/react'

export default function Configuration() {
  const queryClient = useQueryClient()
  const [config, setConfig] = useState('')
  const [hasChanges, setHasChanges] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  const { data: configData, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: () => api.getConfig().then(res => res.data),
  })

  useEffect(() => {
    if (configData) {
      setConfig(JSON.stringify(configData, null, 2))
    }
  }, [configData])

  const validateMutation = useMutation({
    mutationFn: (configText: string) => {
      try {
        const parsedConfig = JSON.parse(configText)
        return api.validateConfig(parsedConfig)
      } catch (e) {
        throw new Error('Invalid JSON format')
      }
    },
    onSuccess: () => {
      setValidationError(null)
    },
    onError: (error: any) => {
      setValidationError(error.response?.data?.message || error.message || 'Validation failed')
    },
  })

  const saveMutation = useMutation({
    mutationFn: (configText: string) => {
      const parsedConfig = JSON.parse(configText)
      return api.updateConfig(parsedConfig)
    },
    onSuccess: () => {
      setHasChanges(false)
      setValidationError(null)
      queryClient.invalidateQueries({ queryKey: ['config'] })
    },
    onError: (error: any) => {
      setValidationError(error.response?.data?.message || error.message || 'Save failed')
    },
  })

  const reloadMutation = useMutation({
    mutationFn: () => api.reloadConfig(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] })
      queryClient.invalidateQueries({ queryKey: ['servers'] })
    },
  })

  const handleConfigChange = (value: string) => {
    setConfig(value)
    setHasChanges(true)
    setValidationError(null)
  }

  const handleValidate = () => {
    validateMutation.mutate(config)
  }

  const handleSave = () => {
    try {
      JSON.parse(config)
      saveMutation.mutate(config)
    } catch (e) {
      setValidationError('Invalid JSON format')
    }
  }

  const handleReload = () => {
    if (confirm('Reload configuration from file? This will restart all servers.')) {
      reloadMutation.mutate()
    }
  }

  return (
    <Box>
      <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <Box>
          <Heading style={{ fontSize: '32px', marginBottom: '8px' }}>Configuration</Heading>
          <Text style={{ color: '#656d76' }}>Edit composer configuration</Text>
        </Box>
        
        <Box style={{ display: 'flex', gap: '8px' }}>
          <Button
            onClick={handleValidate}
            disabled={validateMutation.isPending || !hasChanges}
            leadingVisual={validateMutation.isPending ? SyncIcon : CheckCircleIcon}
          >
            Validate
          </Button>
          
          <Button
            onClick={handleSave}
            disabled={saveMutation.isPending || !hasChanges}
            variant="primary"
            leadingVisual={saveMutation.isPending ? SyncIcon : CheckIcon}
          >
            Save
          </Button>
          
          <Button
            onClick={handleReload}
            disabled={reloadMutation.isPending}
            leadingVisual={SyncIcon}
          >
            Reload from File
          </Button>
        </Box>
      </Box>

      {hasChanges && !validationError && (
        <Flash variant="warning" style={{ marginBottom: '16px' }}>
          <Box style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileCodeIcon size={16} />
            <Text>You have unsaved changes</Text>
          </Box>
        </Flash>
      )}

      {validationError && (
        <Flash variant="danger" style={{ marginBottom: '16px' }}>
          <Box style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
            <AlertIcon size={20} />
            <Box>
              <Text style={{ fontWeight: 'bold', display: 'block' }}>Validation Error</Text>
              <Text style={{ fontSize: '14px', marginTop: '4px', display: 'block' }}>{validationError}</Text>
            </Box>
          </Box>
        </Flash>
      )}

      {validateMutation.isSuccess && !validationError && (
        <Flash variant="success" style={{ marginBottom: '16px' }}>
          <Box style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircleIcon size={16} />
            <Text>Configuration is valid</Text>
          </Box>
        </Flash>
      )}

      {saveMutation.isSuccess && (
        <Flash variant="success" style={{ marginBottom: '16px' }}>
          <Box style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircleIcon size={16} />
            <Text>Configuration saved successfully</Text>
          </Box>
        </Flash>
      )}

      {reloadMutation.isSuccess && (
        <Flash variant="success" style={{ marginBottom: '16px' }}>
          <Box style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircleIcon size={16} />
            <Text>Configuration reloaded from file</Text>
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
                Configuration (JSON format)
              </Text>
              <Text style={{ fontSize: '12px', color: '#656d76', marginTop: '4px', display: 'block' }}>
                Edit the configuration below. Remember to validate before saving.
              </Text>
            </Box>
            <Textarea
              value={config}
              onChange={(e) => handleConfigChange(e.target.value)}
              style={{
                width: '100%',
                height: '600px',
                padding: '16px',
                fontFamily: 'monospace',
                fontSize: '14px',
                border: 'none',
                resize: 'none',
              }}
              placeholder="Loading configuration..."
            />
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
          <li>Edit configuration in JSON format</li>
          <li>Click "Validate" to check for errors before saving</li>
          <li>Click "Save" to update the configuration</li>
          <li>Click "Reload from File" to discard changes and reload from disk</li>
          <li>Changes to server configuration may require server restarts</li>
        </Box>
      </Box>
    </Box>
  )
}
