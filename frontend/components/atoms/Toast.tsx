'use client'

import React from 'react'
import { Check, AlertCircle } from 'lucide-react'

interface ToastProps {
  message: string | null
}

export const Toast: React.FC<ToastProps> = ({ message }) => {
  if (!message) return null
  const isError = message.toLowerCase().includes('failed') || message.toLowerCase().includes('error')

  return (
    <div
      className="toast-badge"
      style={isError ? { background: '#4c0519', borderColor: '#f43f5e', color: '#ffe4e6' } : undefined}
    >
      {isError ? <AlertCircle size={16} style={{ color: '#fb7185' }} /> : <Check size={16} />}
      {message}
    </div>
  )
}

