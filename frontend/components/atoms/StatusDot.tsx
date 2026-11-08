'use client'

import React from 'react'

interface StatusDotProps {
  color?: string
  className?: string
}

export const StatusDot: React.FC<StatusDotProps> = ({ color, className = '' }) => {
  return (
    <span
      className={`status-dot ${className}`.trim()}
      style={color ? { background: color, boxShadow: 'none' } : undefined}
    />
  )
}

