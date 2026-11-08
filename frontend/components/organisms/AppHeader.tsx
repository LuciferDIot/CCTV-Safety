'use client'

import React from 'react'
import {
  ScanLine,
  Video,
  Play,
  Loader2,
  Edit3,
  Upload,
  ChevronDown,
} from 'lucide-react'
import { ExportButtonGroup } from '@/components/molecules'
import { Button } from '@/components/atoms'
import type { TelemetryHUD } from '@/lib/api'

interface AppHeaderProps {
  telemetry: TelemetryHUD
  selectedVideo: string
  renderPreset: 'preview' | 'full'
  isRendering: boolean
  mode: 'view' | 'edit'
  isUploading: boolean
  fileInputRef: React.RefObject<HTMLInputElement | null>
  onSelectRenderPreset: (val: 'preview' | 'full') => void
  onStartRender: () => void
  onSetMode: (m: 'view' | 'edit') => void
  onSwitchVideo: () => void
  onUploadClick: () => void
  onFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => void
}

export const AppHeader: React.FC<AppHeaderProps> = ({
  telemetry,
  selectedVideo,
  renderPreset,
  isRendering,
  mode,
  isUploading,
  fileInputRef,
  onSelectRenderPreset,
  onStartRender,
  onSetMode,
  onSwitchVideo,
  onUploadClick,
  onFileUpload,
}) => {
  return (
    <header className="topbar">
      <div className="brand-lockup">
        <div className="brand-mark">
          <ScanLine size={18} />
        </div>
        <div>
          <div className="eyebrow">CCTV MOTORCYCLE WRONG-WAY &amp; CROSSWALK ANALYZER</div>
          <h1>
            AURA-Traffic <span>Intersection Safety Suite</span>
          </h1>
        </div>
      </div>

      <div className="header-controls">
        <span className="live-pill" style={{ color: '#6ee7b7', borderColor: '#065f46' }}>
          <i /> {telemetry.active_model}
        </span>

        <input
          type="file"
          ref={fileInputRef}
          style={{ display: 'none' }}
          accept=".mp4,.avi,.mov"
          onChange={onFileUpload}
        />

        {selectedVideo ? (
          <>
            <div className="active-video-pill">
              <Video size={13} style={{ color: '#38bdf8' }} />
              <span className="active-video-name" title={selectedVideo}>
                {selectedVideo}
              </span>
              <Button
                className="switch-video-btn"
                onClick={onSwitchVideo}
                title="Change or upload a different video"
              >
                Change Video
              </Button>
            </div>

            <div className="clip-select" style={{ padding: '4px 6px' }}>
              <select
                value={renderPreset}
                onChange={(e) => onSelectRenderPreset(e.target.value as any)}
                title="Select rendering frame limit"
                style={{ fontSize: 10, maxWidth: 130 }}
              >
                <option value="preview">Fast Preview (100 fr)</option>
                <option value="full">Full Video (All fr)</option>
              </select>
              <ChevronDown size={12} />
            </div>

            <Button
              className="render-cta-btn"
              onClick={onStartRender}
              disabled={isRendering}
              title="Trigger AI detection, ByteTrack tracking, and safety rule analysis"
            >
              {isRendering ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
              {isRendering ? 'Rendering...' : 'Render Video'}
            </Button>

            <div className="mode-toggle">
              <Button variant="ghost" className={mode === 'view' ? 'active' : ''} onClick={() => onSetMode('view')}>
                <Video size={13} /> Playback View
              </Button>
              <Button variant="ghost" className={mode === 'edit' ? 'active' : ''} onClick={() => onSetMode('edit')}>
                <Edit3 size={13} /> Edit Zones
              </Button>
            </div>

            <ExportButtonGroup />
          </>
        ) : (
          <Button
            variant="icon"
            title="Upload CCTV video file"
            onClick={onUploadClick}
            disabled={isUploading}
            style={{ border: '1px solid #26303c', padding: '7px 12px', fontSize: 11, gap: 6, display: 'inline-flex' }}
          >
            <Upload size={14} /> {isUploading ? 'Uploading...' : 'Upload Video'}
          </Button>
        )}
      </div>
    </header>
  )
}

