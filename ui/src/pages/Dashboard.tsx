import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { Activity, Server, Wrench, AlertCircle, TrendingUp, CheckCircle, XCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

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

  const stats = [
    {
      name: 'Active Servers',
      value: status?.servers_running || 0,
      total: status?.servers_total || 0,
      icon: Server,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50 dark:bg-blue-950',
    },
    {
      name: 'Total Tools',
      value: status?.total_tools || 0,
      icon: Wrench,
      color: 'text-green-600',
      bgColor: 'bg-green-50 dark:bg-green-950',
    },
    {
      name: 'System Health',
      value: health?.status || 'unknown',
      icon: health?.status === 'healthy' ? Activity : AlertCircle,
      color: health?.status === 'healthy' ? 'text-green-600' : 'text-red-600',
      bgColor: health?.status === 'healthy' ? 'bg-green-50 dark:bg-green-950' : 'bg-red-50 dark:bg-red-950',
    },
    {
      name: 'API Requests',
      value: metrics?.http_requests_total || 0,
      icon: TrendingUp,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50 dark:bg-purple-950',
    },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Dashboard</h1>
        <p className="mt-2 text-muted-foreground">
          Overview of your MCP Compose
        </p>
      </div>

      {/* Stats */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => {
          const Icon = stat.icon
          return (
            <div
              key={stat.name}
              className={`bg-card border border-border rounded-lg p-6 hover:shadow-md transition-shadow`}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <p className="text-sm font-medium text-muted-foreground">
                    {stat.name}
                  </p>
                  <p className="mt-2 text-3xl font-bold text-foreground">
                    {stat.value}
                    {stat.total !== undefined && (
                      <span className="text-lg text-muted-foreground ml-1">
                        / {stat.total}
                      </span>
                    )}
                  </p>
                </div>
                <div className={`p-3 rounded-full ${stat.bgColor}`}>
                  <Icon className={`h-6 w-6 ${stat.color}`} />
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Quick Info & Actions */}
      <div className="grid gap-6 md:grid-cols-2">
        <div className="bg-card border border-border rounded-lg p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4">
            System Information
          </h2>
          <dl className="space-y-3">
            <div className="flex justify-between items-center">
              <dt className="text-sm text-muted-foreground">Version</dt>
              <dd className="font-medium text-sm">{status?.version || 'N/A'}</dd>
            </div>
            <div className="flex justify-between items-center">
              <dt className="text-sm text-muted-foreground">Uptime</dt>
              <dd className="font-medium text-sm">{status?.uptime || 'N/A'}</dd>
            </div>
            <div className="flex justify-between items-center">
              <dt className="text-sm text-muted-foreground">Platform</dt>
              <dd className="font-medium text-sm">{status?.platform || 'N/A'}</dd>
            </div>
            <div className="flex justify-between items-center">
              <dt className="text-sm text-muted-foreground">Total Prompts</dt>
              <dd className="font-medium text-sm">{status?.total_prompts || 0}</dd>
            </div>
            <div className="flex justify-between items-center">
              <dt className="text-sm text-muted-foreground">Total Resources</dt>
              <dd className="font-medium text-sm">{status?.total_resources || 0}</dd>
            </div>
          </dl>
        </div>

        <div className="bg-card border border-border rounded-lg p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4">
            Quick Actions
          </h2>
          <div className="space-y-2">
            <button
              onClick={() => navigate('/servers')}
              className="w-full px-4 py-3 text-left rounded-md hover:bg-accent transition-colors flex items-center justify-between group"
            >
              <span className="text-foreground">View All Servers</span>
              <span className="text-muted-foreground group-hover:text-foreground transition-colors">
                →
              </span>
            </button>
            <button
              onClick={() => navigate('/tools')}
              className="w-full px-4 py-3 text-left rounded-md hover:bg-accent transition-colors flex items-center justify-between group"
            >
              <span className="text-foreground">Browse Tools</span>
              <span className="text-muted-foreground group-hover:text-foreground transition-colors">
                →
              </span>
            </button>
            <button
              onClick={() => navigate('/metrics')}
              className="w-full px-4 py-3 text-left rounded-md hover:bg-accent transition-colors flex items-center justify-between group"
            >
              <span className="text-foreground">View Metrics</span>
              <span className="text-muted-foreground group-hover:text-foreground transition-colors">
                →
              </span>
            </button>
            <button
              onClick={() => navigate('/logs')}
              className="w-full px-4 py-3 text-left rounded-md hover:bg-accent transition-colors flex items-center justify-between group"
            >
              <span className="text-foreground">Check Logs</span>
              <span className="text-muted-foreground group-hover:text-foreground transition-colors">
                →
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* Server Status Overview */}
      {composition?.servers && composition.servers.length > 0 && (
        <div className="bg-card border border-border rounded-lg p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4">
            Server Status
          </h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {composition.servers.map((server: any) => (
              <div
                key={server.name}
                className="p-4 rounded-lg border border-border hover:border-muted-foreground transition-colors"
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-medium text-foreground">{server.name}</h3>
                  {server.status === 'running' ? (
                    <CheckCircle className="h-5 w-5 text-green-600" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-600" />
                  )}
                </div>
                <div className="space-y-1 text-sm text-muted-foreground">
                  <p>Tools: {server.tool_count || 0}</p>
                  <p>Status: {server.status || 'unknown'}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Activity / Metrics Summary */}
      {metrics && (
        <div className="bg-card border border-border rounded-lg p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4">
            Performance Metrics
          </h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <div className="p-4 rounded-lg bg-muted">
              <p className="text-sm text-muted-foreground">HTTP Requests</p>
              <p className="text-2xl font-bold text-foreground mt-1">
                {metrics.http_requests_total || 0}
              </p>
            </div>
            <div className="p-4 rounded-lg bg-muted">
              <p className="text-sm text-muted-foreground">Tool Invocations</p>
              <p className="text-2xl font-bold text-foreground mt-1">
                {metrics.tool_invocations_total || 0}
              </p>
            </div>
            <div className="p-4 rounded-lg bg-muted">
              <p className="text-sm text-muted-foreground">Auth Attempts</p>
              <p className="text-2xl font-bold text-foreground mt-1">
                {metrics.auth_attempts_total || 0}
              </p>
            </div>
            <div className="p-4 rounded-lg bg-muted">
              <p className="text-sm text-muted-foreground">Server Restarts</p>
              <p className="text-2xl font-bold text-foreground mt-1">
                {metrics.server_restarts_total || 0}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
