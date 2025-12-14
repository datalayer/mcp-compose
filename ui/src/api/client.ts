import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor for auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized
      localStorage.removeItem('auth_token')
      window.location.href = '/ui/login'
    }
    return Promise.reject(error)
  }
)

// API methods
export const api = {
  // Auth
  login: (username: string, password: string) => 
    apiClient.post('/auth/login', { username, password }),
  logout: () => apiClient.post('/auth/logout'),
  getCurrentUser: () => apiClient.get('/auth/me'),
  
  // Health
  getHealth: () => apiClient.get('/health'),
  
  // Version
  getVersion: () => apiClient.get('/version'),
  
  // Servers
  listServers: () => apiClient.get('/servers'),
  getServer: (id: string) => apiClient.get(`/servers/${id}`),
  startServer: (id: string) => apiClient.post(`/servers/${id}/start`),
  stopServer: (id: string) => apiClient.post(`/servers/${id}/stop`),
  restartServer: (id: string) => apiClient.post(`/servers/${id}/restart`),
  getServerStatus: (id: string) => apiClient.get(`/servers/${id}/status`),
  getServerLogs: (id: string, params?: { lines?: number }) => 
    apiClient.get(`/servers/${id}/logs`, { params }),
  
  // Tools
  listTools: (params?: { server_id?: string; offset?: number; limit?: number }) => 
    apiClient.get('/tools', { params }),
  getTool: (name: string) => apiClient.get(`/tools/${encodeURIComponent(name)}`),
  invokeTool: (name: string, arguments_: Record<string, unknown>) => 
    apiClient.post(`/tools/${encodeURIComponent(name)}/invoke`, { arguments: arguments_ }),
  
  // Prompts
  listPrompts: (params?: { server_name?: string; page?: number; page_size?: number }) => 
    apiClient.get('/prompts', { params }),
  getPrompt: (name: string) => apiClient.get(`/prompts/${encodeURIComponent(name)}`),
  
  // Resources
  listResources: (params?: { server_name?: string; page?: number; page_size?: number }) => 
    apiClient.get('/resources', { params }),
  readResource: (uri: string) => 
    apiClient.post('/resources/read', { uri }),
  
  // Configuration
  getConfig: () => apiClient.get('/config'),
  updateConfig: (config: unknown) => apiClient.put('/config', config),
  validateConfig: (config: unknown) => apiClient.post('/config/validate', config),
  reloadConfig: () => apiClient.post('/config/reload'),
  
  // Status & Composition
  getStatus: () => apiClient.get('/status'),
  getComposition: () => apiClient.get('/status/composition'),
  getDetailedHealth: () => apiClient.get('/status/health'),
  getMetrics: () => apiClient.get('/status/metrics'),
  getPrometheusMetrics: () => apiClient.get('/metrics/prometheus', {
    headers: { Accept: 'text/plain' },
    responseType: 'text',
  }),
  
  // Translators
  listTranslators: () => apiClient.get('/translators'),
  createStdioToSse: (data: {
    name: string
    sse_url: string
    headers?: Record<string, string>
    timeout?: number
  }) => apiClient.post('/translators/stdio-to-sse', data),
  createSseToStdio: (data: {
    name: string
    command: string
    args?: string[]
    env?: Record<string, string>
    cwd?: string
  }) => apiClient.post('/translators/sse-to-stdio', data),
  deleteTranslator: (name: string) => apiClient.delete(`/translators/${name}`),
  translateMessage: (name: string, message: unknown) => 
    apiClient.post(`/translators/${name}/translate`, message),
  
  // Settings
  getSettings: () => apiClient.get('/settings'),
  updateSettings: (settings: {
    api_endpoint?: string
    refresh_interval?: number
    enable_notifications?: boolean
    enable_sounds?: boolean
    max_log_lines?: number
  }) => apiClient.put('/settings', settings),
  resetSettings: () => apiClient.post('/settings/reset'),
}

export default api
