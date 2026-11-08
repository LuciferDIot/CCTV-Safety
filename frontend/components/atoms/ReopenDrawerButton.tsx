'use client'

import React from 'react'
import { Eye } from 'lucide-react'
import { Button } from '@/components/atoms/Button'

interface ReopenDrawerButtonProps {
  eventId?: string
  onClick: () => void
}

export const ReopenDrawerButton: React.FC<ReopenDrawerButtonProps> = ({ eventId, onClick }) => {
  return (
    <Button variant="reopen" onClick={onClick}>
      <Eye size={13} /> View 3-Frame Temporal Evidence Strip &amp; Kinematics ({eventId || 'No event'})
    </Button>
  )
}
