'use client'

import React from 'react'

interface DashboardLayoutProps {
  toast: React.ReactNode
  header: React.ReactNode
  telemetry: React.ReactNode
  progressBanner?: React.ReactNode
  canvas: React.ReactNode
  evidenceDrawer: React.ReactNode
  sidebar: React.ReactNode
}

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({
  toast,
  header,
  telemetry,
  progressBanner,
  canvas,
  evidenceDrawer,
  sidebar,
}) => {
  return (
    <main className="dashboard-shell">
      {toast}
      {header}
      {telemetry}
      <div className="workspace">
        <div className="main-column">
          {progressBanner}
          {canvas}
          {evidenceDrawer}
        </div>
        {sidebar}
      </div>
    </main>
  )
}

