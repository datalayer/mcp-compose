import { Box, Text } from '@primer/react'
import { AlertIcon } from '@primer/octicons-react'

interface DemoBannerProps {
  message?: string
}

export default function DemoBanner({ 
  message = "This page contains demo/mock content for demonstration purposes." 
}: DemoBannerProps) {
  return (
    <Box
      style={{
        backgroundColor: 'rgba(157, 106, 0, 0.1)',
        border: '1px solid rgba(157, 106, 0, 0.3)',
        borderRadius: '6px',
        padding: '12px 16px',
        marginBottom: '24px',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
      }}
    >
      <Box style={{ color: '#9a6700', flexShrink: 0 }}>
        <AlertIcon size={20} />
      </Box>
      <Text style={{ fontSize: '14px', color: '#7d4e00' }}>
        <strong>Demo Mode:</strong> {message}
      </Text>
    </Box>
  )
}
