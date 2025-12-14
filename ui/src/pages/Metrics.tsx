import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { api } from '../api/client'
import { GraphIcon, ArrowUpIcon, ArrowDownIcon, ClockIcon, ZapIcon, ServerIcon, AlertIcon } from '@primer/octicons-react'

interface MetricsData {
  timestamp: string
  requests: number
  tools: number
  latency: number
  memory: number
  cpu: number
}

export default function Metrics() {
  const [timeRange, setTimeRange] = useState<'1h' | '6h' | '24h' | '7d'>('1h')
  const [metricsHistory, setMetricsHistory] = useState<MetricsData[]>([])

  // Fetch current metrics
  const { data: metrics, isLoading } = useQuery({
    queryKey: ['metrics'],
    queryFn: () => api.getMetrics().then(res => res.data),
    refetchInterval: 5000,
  })

  const { data: status } = useQuery({
    queryKey: ['status'],
    queryFn: () => api.getStatus().then(res => res.data),
    refetchInterval: 5000,
  })

  // Build metrics history for charts
  useEffect(() => {
    if (metrics) {
      const now = new Date()
      const newDataPoint: MetricsData = {
        timestamp: now.toLocaleTimeString(),
        requests: metrics.http_requests_total || 0,
        tools: metrics.tool_invocations_total || 0,
        latency: Math.random() * 100 + 20, // Mock latency
        memory: Math.random() * 50 + 30, // Mock memory %
        cpu: Math.random() * 40 + 10, // Mock CPU %
      }

      setMetricsHistory(prev => {
        const updated = [...prev, newDataPoint]
        // Keep last 60 data points
        return updated.slice(-60)
      })
    }
  }, [metrics])

  // Calculate trends
  const calculateTrend = (current: number, previous: number): { value: number; isUp: boolean } => {
    if (!previous) return { value: 0, isUp: true }
    const diff = ((current - previous) / previous) * 100
    return { value: Math.abs(diff), isUp: diff > 0 }
  }

  const requestsTrend = metricsHistory.length > 1
    ? calculateTrend(
        metricsHistory[metricsHistory.length - 1].requests,
        metricsHistory[metricsHistory.length - 2].requests
      )
    : { value: 0, isUp: true }

  const toolsTrend = metricsHistory.length > 1
    ? calculateTrend(
        metricsHistory[metricsHistory.length - 1].tools,
        metricsHistory[metricsHistory.length - 2].tools
      )
    : { value: 0, isUp: true }

  const avgLatency = metricsHistory.length > 0
    ? metricsHistory.reduce((sum, m) => sum + m.latency, 0) / metricsHistory.length
    : 0

  const avgCpu = metricsHistory.length > 0
    ? metricsHistory.reduce((sum, m) => sum + m.cpu, 0) / metricsHistory.length
    : 0

  const avgMemory = metricsHistory.length > 0
    ? metricsHistory.reduce((sum, m) => sum + m.memory, 0) / metricsHistory.length
    : 0

  // ECharts options
  const requestRateOption: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1f1f1f',
      borderColor: '#333',
      textStyle: { color: '#fff' }
    },
    legend: { textStyle: { color: '#888' } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: metricsHistory.map(m => m.timestamp),
      axisLine: { lineStyle: { color: '#888' } },
      axisLabel: { color: '#888' }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#888' } },
      axisLabel: { color: '#888' },
      splitLine: { lineStyle: { color: '#333' } }
    },
    series: [{
      name: 'Requests',
      type: 'line',
      smooth: true,
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
            { offset: 1, color: 'rgba(59, 130, 246, 0)' }
          ]
        }
      },
      lineStyle: { color: '#3b82f6' },
      itemStyle: { color: '#3b82f6' },
      data: metricsHistory.map(m => m.requests)
    }]
  }

  const toolInvocationsOption: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1f1f1f',
      borderColor: '#333',
      textStyle: { color: '#fff' }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: metricsHistory.slice(-20).map(m => m.timestamp),
      axisLine: { lineStyle: { color: '#888' } },
      axisLabel: { color: '#888' }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#888' } },
      axisLabel: { color: '#888' },
      splitLine: { lineStyle: { color: '#333' } }
    },
    series: [{
      name: 'Invocations',
      type: 'bar',
      itemStyle: { color: '#a855f7' },
      data: metricsHistory.slice(-20).map(m => m.tools)
    }]
  }

  const latencyOption: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1f1f1f',
      borderColor: '#333',
      textStyle: { color: '#fff' }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: metricsHistory.slice(-20).map(m => m.timestamp),
      axisLine: { lineStyle: { color: '#888' } },
      axisLabel: { color: '#888' }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#888' } },
      axisLabel: { color: '#888' },
      splitLine: { lineStyle: { color: '#333' } }
    },
    series: [{
      name: 'Latency (ms)',
      type: 'line',
      smooth: true,
      lineStyle: { color: '#eab308', width: 2 },
      itemStyle: { color: '#eab308' },
      showSymbol: false,
      data: metricsHistory.slice(-20).map(m => m.latency)
    }]
  }

  const resourcesOption: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1f1f1f',
      borderColor: '#333',
      textStyle: { color: '#fff' }
    },
    legend: { textStyle: { color: '#888' } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: metricsHistory.map(m => m.timestamp),
      axisLine: { lineStyle: { color: '#888' } },
      axisLabel: { color: '#888' }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#888' } },
      axisLabel: { color: '#888' },
      splitLine: { lineStyle: { color: '#333' } }
    },
    series: [
      {
        name: 'CPU %',
        type: 'line',
        smooth: true,
        lineStyle: { color: '#10b981', width: 2 },
        itemStyle: { color: '#10b981' },
        showSymbol: false,
        data: metricsHistory.map(m => m.cpu)
      },
      {
        name: 'Memory %',
        type: 'line',
        smooth: true,
        lineStyle: { color: '#f59e0b', width: 2 },
        itemStyle: { color: '#f59e0b' },
        showSymbol: false,
        data: metricsHistory.map(m => m.memory)
      }
    ]
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <GraphIcon size={32} className="animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Metrics</h1>
          <p className="mt-2 text-muted-foreground">
            System performance and usage statistics
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value as '1h' | '6h' | '24h' | '7d')}
            className="px-4 py-2 bg-background border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="1h">Last Hour</option>
            <option value="6h">Last 6 Hours</option>
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
          </select>
        </div>
      </div>

      {/* Key Metrics Cards */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Total Requests</p>
              <p className="text-3xl font-bold mt-2">{metrics?.http_requests_total || 0}</p>
              <div className="flex items-center gap-1 mt-2">
                {requestsTrend.isUp ? (
                  <ArrowUpIcon size={16} className="text-green-500" />
                ) : (
                  <ArrowDownIcon size={16} className="text-red-500" />
                )}
                <span className={`text-sm ${requestsTrend.isUp ? 'text-green-500' : 'text-red-500'}`}>
                  {requestsTrend.value.toFixed(1)}%
                </span>
              </div>
            </div>
            <div className="p-3 bg-blue-500/10 rounded-lg">
              <GraphIcon size={24} className="text-blue-500" />
            </div>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Tool Invocations</p>
              <p className="text-3xl font-bold mt-2">{metrics?.tool_invocations_total || 0}</p>
              <div className="flex items-center gap-1 mt-2">
                {toolsTrend.isUp ? (
                  <ArrowUpIcon size={16} className="text-green-500" />
                ) : (
                  <ArrowDownIcon size={16} className="text-red-500" />
                )}
                <span className={`text-sm ${toolsTrend.isUp ? 'text-green-500' : 'text-red-500'}`}>
                  {toolsTrend.value.toFixed(1)}%
                </span>
              </div>
            </div>
            <div className="p-3 bg-purple-500/10 rounded-lg">
              <ZapIcon size={24} className="text-purple-500" />
            </div>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Avg Latency</p>
              <p className="text-3xl font-bold mt-2">{avgLatency.toFixed(0)}ms</p>
              <p className="text-sm text-muted-foreground mt-2">Response time</p>
            </div>
            <div className="p-3 bg-yellow-500/10 rounded-lg">
              <ClockIcon size={24} className="text-yellow-500" />
            </div>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Active Servers</p>
              <p className="text-3xl font-bold mt-2">{status?.servers_running || 0}</p>
              <p className="text-sm text-muted-foreground mt-2">
                of {status?.servers_total || 0} total
              </p>
            </div>
            <div className="p-3 bg-green-500/10 rounded-lg">
              <ServerIcon size={24} className="text-green-500" />
            </div>
          </div>
        </div>
      </div>

      {/* Request Rate Chart */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">Request Rate Over Time</h2>
        {metricsHistory.length > 0 ? (
          <ReactECharts option={requestRateOption} style={{ height: 300 }} />
        ) : (
          <div className="flex items-center justify-center h-[300px] text-muted-foreground">
            <div className="text-center">
              <AlertIcon size={48} className="mx-auto mb-4" />
              <p>Collecting metrics data...</p>
            </div>
          </div>
        )}
      </div>

      {/* Tool Invocations and Latency */}
      <div className="grid gap-6 md:grid-cols-2">
        <div className="bg-card border border-border rounded-lg p-6">
          <h2 className="text-xl font-bold mb-4">Tool Invocations</h2>
          {metricsHistory.length > 0 ? (
            <ReactECharts option={toolInvocationsOption} style={{ height: 250 }} />
          ) : (
            <div className="flex items-center justify-center h-[250px] text-muted-foreground">
              <p>No data available</p>
            </div>
          )}
        </div>

        <div className="bg-card border border-border rounded-lg p-6">
          <h2 className="text-xl font-bold mb-4">Response Latency</h2>
          {metricsHistory.length > 0 ? (
            <ReactECharts option={latencyOption} style={{ height: 250 }} />
          ) : (
            <div className="flex items-center justify-center h-[250px] text-muted-foreground">
              <p>No data available</p>
            </div>
          )}
        </div>
      </div>

      {/* System Resources */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">System Resources</h2>
        {metricsHistory.length > 0 ? (
          <ReactECharts option={resourcesOption} style={{ height: 300 }} />
        ) : (
          <div className="flex items-center justify-center h-[300px] text-muted-foreground">
            <div className="text-center">
              <AlertIcon size={48} className="mx-auto mb-4" />
              <p>Collecting resource metrics...</p>
            </div>
          </div>
        )}
      </div>

      {/* Performance Summary */}
      <div className="grid gap-6 md:grid-cols-3">
        <div className="bg-card border border-border rounded-lg p-6">
          <h3 className="font-semibold mb-2">Average CPU Usage</h3>
          <p className="text-3xl font-bold text-green-500">{avgCpu.toFixed(1)}%</p>
          <div className="mt-2 h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 transition-all duration-300"
              style={{ width: `${Math.min(avgCpu, 100)}%` }}
            />
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-6">
          <h3 className="font-semibold mb-2">Average Memory Usage</h3>
          <p className="text-3xl font-bold text-orange-500">{avgMemory.toFixed(1)}%</p>
          <div className="mt-2 h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-orange-500 transition-all duration-300"
              style={{ width: `${Math.min(avgMemory, 100)}%` }}
            />
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-6">
          <h3 className="font-semibold mb-2">Uptime</h3>
          <p className="text-3xl font-bold text-blue-500">{status?.uptime || '0m'}</p>
          <p className="text-sm text-muted-foreground mt-2">System running</p>
        </div>
      </div>
    </div>
  )
}
