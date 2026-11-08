'use client'

import React from 'react'
import { StatusDot } from './StatusDot'

interface BadgeProps {
  status: string
}

export function getTone(status: string) {
  if (status === 'CONFIRMED') return 'red'
  if (status === 'EXEMPT') return 'green'
  if (status === 'INSUFFICIENT_EVIDENCE') return 'amber'
  return 'slate'
}

export function getColor(status: string) {
  if (status === 'CONFIRMED') return '#fb7185'
  if (status === 'EXEMPT') return '#34d399'
  if (status === 'INSUFFICIENT_EVIDENCE') return '#fbbf24'
  return '#94a3b8'
}

export const Badge: React.FC<BadgeProps> = ({ status }) => {
  const tone = getTone(status)
  return (
    <span className={`status-badge ${tone}`}>
      <StatusDot color={getColor(status)} />
      {status}
    </span>
  )
}

