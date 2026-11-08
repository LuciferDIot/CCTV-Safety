'use client'

import React from 'react'
import { FileJson, FileSpreadsheet } from 'lucide-react'
import { Button } from '@/components/atoms/Button'
import { getExportUrl } from '@/lib/api'

export const ExportButtonGroup: React.FC<{ selectedVideo?: string }> = ({ selectedVideo }) => {
  const baseStem = selectedVideo ? selectedVideo.replace(/\.[^/.]+$/, '').replace(/^(annotated_)/, '').replace(/(_annotated)$/, '') : ''
  return (
    <div className="export-actions">
      <a href={getExportUrl('json', selectedVideo)} download={selectedVideo ? `events_${baseStem}.json` : "detected_events.json"} style={{ textDecoration: 'none' }}>
        <Button title="Export events JSON" variant="ghost">
          <FileJson size={14} /> JSON
        </Button>
      </a>
      <a href={getExportUrl('csv', selectedVideo)} download={selectedVideo ? `events_${baseStem}.csv` : "detected_events.csv"} style={{ textDecoration: 'none' }}>
        <Button title="Export events CSV" variant="ghost">
          <FileSpreadsheet size={14} /> CSV
        </Button>
      </a>
    </div>
  )
}

