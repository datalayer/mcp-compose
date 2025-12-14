import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { CheckIcon, SyncIcon, CheckCircleIcon, AlertIcon, FileCodeIcon } from '@primer/octicons-react'
import { useState, useEffect } from 'react'

export default function Configuration() {
  const queryClient = useQueryClient()
  const [config, setConfig] = useState('')
  const [hasChanges, setHasChanges] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  // Fetch current config
  const { data: configData, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: () => api.getConfig().then(res => res.data),
  })

  // Update config when loaded
  useEffect(() => {
    if (configData) {
      // Convert config object to TOML-like string for display
      setConfig(JSON.stringify(configData, null, 2))
    }
  }, [configData])

  // Validate mutation
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

  // Save mutation
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

  // Reload mutation
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
      JSON.parse(config) // Validate JSON first
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Configuration</h1>
          <p className="mt-2 text-muted-foreground">
            Edit composer configuration
          </p>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={handleValidate}
            disabled={validateMutation.isPending || !hasChanges}
            className="flex items-center gap-2 px-4 py-2 bg-card border border-border rounded-md hover:bg-accent transition-colors disabled:opacity-50"
          >
            {validateMutation.isPending ? (
              <SyncIcon size={16} className="animate-spin" />
            ) : (
              <CheckCircleIcon size={16} />
            )}
            Validate
          </button>
          
          <button
            onClick={handleSave}
            disabled={saveMutation.isPending || !hasChanges}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {saveMutation.isPending ? (
              <SyncIcon size={16} className="animate-spin" />
            ) : (
              <CheckIcon size={16} />
            )}
            Save
          </button>
          
          <button
            onClick={handleReload}
            disabled={reloadMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-card border border-border rounded-md hover:bg-accent transition-colors disabled:opacity-50"
          >
            {reloadMutation.isPending ? (
              <SyncIcon size={16} className="animate-spin" />
            ) : (
              <SyncIcon size={16} />
            )}
            Reload from File
          </button>
        </div>
      </div>

      {/* Status Messages */}
      {hasChanges && !validationError && (
        <div className="p-4 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-md">
          <p className="text-sm text-blue-900 dark:text-blue-100">
            <FileCodeIcon size={16} className="inline mr-2" />
            You have unsaved changes
          </p>
        </div>
      )}

      {validationError && (
        <div className="p-4 bg-destructive/10 border border-destructive rounded-md">
          <div className="flex items-start gap-2">
            <AlertIcon size={20} className="text-destructive flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-destructive">Validation Error</p>
              <p className="text-sm text-destructive/80 mt-1">{validationError}</p>
            </div>
          </div>
        </div>
      )}

      {validateMutation.isSuccess && !validationError && (
        <div className="p-4 bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-md">
          <p className="text-sm text-green-900 dark:text-green-100">
            <CheckCircleIcon size={16} className="inline mr-2" />
            Configuration is valid
          </p>
        </div>
      )}

      {saveMutation.isSuccess && (
        <div className="p-4 bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-md">
          <p className="text-sm text-green-900 dark:text-green-100">
            <CheckCircleIcon size={16} className="inline mr-2" />
            Configuration saved successfully
          </p>
        </div>
      )}

      {reloadMutation.isSuccess && (
        <div className="p-4 bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-md">
          <p className="text-sm text-green-900 dark:text-green-100">
            <CheckCircleIcon size={16} className="inline mr-2" />
            Configuration reloaded from file
          </p>
        </div>
      )}

      {/* Editor */}
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <SyncIcon size={32} className="animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div>
            <div className="bg-muted px-4 py-2 border-b border-border">
              <p className="text-sm font-medium text-foreground">
                Configuration (JSON format)
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Edit the configuration below. Remember to validate before saving.
              </p>
            </div>
            <textarea
              value={config}
              onChange={(e) => handleConfigChange(e.target.value)}
              className="w-full h-[600px] p-4 font-mono text-sm bg-background text-foreground focus:outline-none resize-none"
              spellCheck={false}
              placeholder="Loading configuration..."
            />
          </div>
        )}
      </div>

      {/* Help Text */}
      <div className="bg-muted border border-border rounded-lg p-4">
        <h3 className="text-sm font-semibold text-foreground mb-2">Configuration Guide</h3>
        <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
          <li>Edit configuration in JSON format</li>
          <li>Click "Validate" to check for errors before saving</li>
          <li>Click "Save" to update the configuration</li>
          <li>Click "Reload from File" to discard changes and reload from disk</li>
          <li>Changes to server configuration may require server restarts</li>
        </ul>
      </div>
    </div>
  )
}
