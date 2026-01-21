/*
 * Copyright (c) 2025-2026 Datalayer, Inc.
 * Distributed under the terms of the Modified BSD License.
 */

import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { api } from '../api/client'
import { GraphIcon, ArrowUpIcon, ArrowDownIcon, ClockIcon, ZapIcon, ServerIcon, AlertIcon } from '@primer/octicons-react'
import { Box, Heading, Text, Select, FormControl, Spinner } from '@primer/react'
import DemoBanner from '../components/DemoBanner'

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
            { offset: 0, color: 'rgba(9, 105, 218, 0.3)' },
            { offset: 1, color: 'rgba(9, 105, 218, 0)' }
          ]
        }
      },
      lineStyle: { color: '#0969da' },
      itemStyle: { color: '#0969da' },
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
      itemStyle: { color: '#8250df' },
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
      lineStyle: { color: '#9a6700', width: 2 },
      itemStyle: { color: '#9a6700' },
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
        lineStyle: { color: '#1a7f37', width: 2 },
        itemStyle: { color: '#1a7f37' },
        showSymbol: false,
        data: metricsHistory.map(m => m.cpu)
      },
      {
        name: 'Memory %',
        type: 'line',
        smooth: true,
        lineStyle: { color: '#bf8700', width: 2 },
        itemStyle: { color: '#bf8700' },
        showSymbol: false,
        data: metricsHistory.map(m => m.memory)
      }
    ]
  }

  if (isLoading) {
    return (
      <Box style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '384px' }}>
        <Spinner size="large" />
      </Box>
    )
  }

  return (
    <Box>
      <DemoBanner message="Metrics currently display demo data for visualization purposes. Real server metrics will be available when backend telemetry is integrated." />
      
      {/* Header */}
      <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <Box>
          <Heading style={{ fontSize: '32px', marginBottom: '8px' }}>Metrics</Heading>
          <Text style={{ color: '#656d76' }}>System performance and usage statistics</Text>
        </Box>
        <FormControl>
          <FormControl.Label visuallyHidden>Time Range</FormControl.Label>
          <Select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value as '1h' | '6h' | '24h' | '7d')}
          >
            <Select.Option value="1h">Last Hour</Select.Option>
            <Select.Option value="6h">Last 6 Hours</Select.Option>
            <Select.Option value="24h">Last 24 Hours</Select.Option>
            <Select.Option value="7d">Last 7 Days</Select.Option>
          </Select>
        </FormControl>
      </Box>

      {/* Key Metrics Cards */}
      <Box style={{ display: 'grid', gap: '24px', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', marginBottom: '24px' }}>
        <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa' }}>
          <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <Box>
              <Text style={{ fontSize: '14px', color: '#656d76', display: 'block' }}>Total Requests</Text>
              <Text style={{ fontSize: '32px', fontWeight: 'bold', marginTop: '8px', display: 'block' }}>
                {metrics?.http_requests_total || 0}
              </Text>
              <Box style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '8px' }}>
                {requestsTrend.isUp ? (
                  <ArrowUpIcon size={16} />
                ) : (
                  <ArrowDownIcon size={16} />
                )}
                <Text style={{ fontSize: '14px', color: requestsTrend.isUp ? '#1a7f37' : '#cf222e' }}>
                  {requestsTrend.value.toFixed(1)}%
                </Text>
              </Box>
            </Box>
            <Box style={{ padding: '12px', backgroundColor: 'rgba(9, 105, 218, 0.1)', borderRadius: '6px' }}>
              <GraphIcon size={24} />
            </Box>
          </Box>
        </Box>

        <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa' }}>
          <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <Box>
              <Text style={{ fontSize: '14px', color: '#656d76', display: 'block' }}>Tool Invocations</Text>
              <Text style={{ fontSize: '32px', fontWeight: 'bold', marginTop: '8px', display: 'block' }}>
                {metrics?.tool_invocations_total || 0}
              </Text>
              <Box style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '8px' }}>
                {toolsTrend.isUp ? (
                  <ArrowUpIcon size={16} />
                ) : (
                  <ArrowDownIcon size={16} />
                )}
                <Text style={{ fontSize: '14px', color: toolsTrend.isUp ? '#1a7f37' : '#cf222e' }}>
                  {toolsTrend.value.toFixed(1)}%
                </Text>
              </Box>
            </Box>
            <Box style={{ padding: '12px', backgroundColor: 'rgba(130, 80, 223, 0.1)', borderRadius: '6px' }}>
              <ZapIcon size={24} />
            </Box>
          </Box>
        </Box>

        <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa' }}>
          <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <Box>
              <Text style={{ fontSize: '14px', color: '#656d76', display: 'block' }}>Avg Latency</Text>
              <Text style={{ fontSize: '32px', fontWeight: 'bold', marginTop: '8px', display: 'block' }}>
                {avgLatency.toFixed(0)}ms
              </Text>
              <Text style={{ fontSize: '14px', color: '#656d76', marginTop: '8px', display: 'block' }}>Response time</Text>
            </Box>
            <Box style={{ padding: '12px', backgroundColor: 'rgba(154, 103, 0, 0.1)', borderRadius: '6px' }}>
              <ClockIcon size={24} />
            </Box>
          </Box>
        </Box>

        <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa' }}>
          <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <Box>
              <Text style={{ fontSize: '14px', color: '#656d76', display: 'block' }}>Active Servers</Text>
              <Text style={{ fontSize: '32px', fontWeight: 'bold', marginTop: '8px', display: 'block' }}>
                {status?.servers_running || 0}
              </Text>
              <Text style={{ fontSize: '14px', color: '#656d76', marginTop: '8px', display: 'block' }}>
                of {status?.servers_total || 0} total
              </Text>
            </Box>
            <Box style={{ padding: '12px', backgroundColor: 'rgba(26, 127, 55, 0.1)', borderRadius: '6px' }}>
              <ServerIcon size={24} />
            </Box>
          </Box>
        </Box>
      </Box>

      {/* Request Rate Chart */}
      <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa', marginBottom: '24px' }}>
        <Heading style={{ fontSize: '20px', marginBottom: '16px' }}>Request Rate Over Time</Heading>
        {metricsHistory.length > 0 ? (
          <ReactECharts option={requestRateOption} style={{ height: 300 }} />
        ) : (
          <Box style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '300px', color: '#656d76' }}>
            <Box style={{ marginBottom: '16px' }}>
              <AlertIcon size={48} />
            </Box>
            <Text>Collecting metrics data...</Text>
          </Box>
        )}
      </Box>

      {/* Tool Invocations and Latency */}
      <Box style={{ display: 'grid', gap: '24px', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', marginBottom: '24px' }}>
        <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa' }}>
          <Heading style={{ fontSize: '20px', marginBottom: '16px' }}>Tool Invocations</Heading>
          {metricsHistory.length > 0 ? (
            <ReactECharts option={toolInvocationsOption} style={{ height: 250 }} />
          ) : (
            <Box style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '250px', color: '#656d76' }}>
              <Text>No data available</Text>
            </Box>
          )}
        </Box>

        <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa' }}>
          <Heading style={{ fontSize: '20px', marginBottom: '16px' }}>Response Latency</Heading>
          {metricsHistory.length > 0 ? (
            <ReactECharts option={latencyOption} style={{ height: 250 }} />
          ) : (
            <Box style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '250px', color: '#656d76' }}>
              <Text>No data available</Text>
            </Box>
          )}
        </Box>
      </Box>

      {/* System Resources */}
      <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa', marginBottom: '24px' }}>
        <Heading style={{ fontSize: '20px', marginBottom: '16px' }}>System Resources</Heading>
        {metricsHistory.length > 0 ? (
          <ReactECharts option={resourcesOption} style={{ height: 300 }} />
        ) : (
          <Box style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '300px', color: '#656d76' }}>
            <Box style={{ marginBottom: '16px' }}>
              <AlertIcon size={48} />
            </Box>
            <Text>Collecting resource metrics...</Text>
          </Box>
        )}
      </Box>

      {/* Performance Summary */}
      <Box style={{ display: 'grid', gap: '24px', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))' }}>
        <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa' }}>
          <Heading style={{ fontSize: '16px', marginBottom: '8px' }}>Average CPU Usage</Heading>
          <Text style={{ fontSize: '32px', fontWeight: 'bold', color: '#1a7f37', display: 'block' }}>
            {avgCpu.toFixed(1)}%
          </Text>
          <Box style={{ marginTop: '8px', height: '8px', backgroundColor: '#eaeef2', borderRadius: '9999px', overflow: 'hidden' }}>
            <Box
              style={{
                height: '100%',
                backgroundColor: '#1a7f37',
                transition: 'width 0.3s',
                width: `${Math.min(avgCpu, 100)}%`
              }}
            />
          </Box>
        </Box>

        <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa' }}>
          <Heading style={{ fontSize: '16px', marginBottom: '8px' }}>Average Memory Usage</Heading>
          <Text style={{ fontSize: '32px', fontWeight: 'bold', color: '#bf8700', display: 'block' }}>
            {avgMemory.toFixed(1)}%
          </Text>
          <Box style={{ marginTop: '8px', height: '8px', backgroundColor: '#eaeef2', borderRadius: '9999px', overflow: 'hidden' }}>
            <Box
              style={{
                height: '100%',
                backgroundColor: '#bf8700',
                transition: 'width 0.3s',
                width: `${Math.min(avgMemory, 100)}%`
              }}
            />
          </Box>
        </Box>

        <Box style={{ padding: '24px', border: '1px solid #d0d7de', borderRadius: '6px', backgroundColor: '#f6f8fa' }}>
          <Heading style={{ fontSize: '16px', marginBottom: '8px' }}>Uptime</Heading>
          <Text style={{ fontSize: '32px', fontWeight: 'bold', color: '#0969da', display: 'block' }}>
            {status?.uptime || '0m'}
          </Text>
          <Text style={{ fontSize: '14px', color: '#656d76', marginTop: '8px', display: 'block' }}>System running</Text>
        </Box>
      </Box>
    </Box>
  )
}
