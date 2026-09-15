import React, { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { fetchHealth } from '../api/client'

const NAV = [
  { path: '/',          icon: '📊', label: 'Overview',       section: 'OPERATIONS' },
  { path: '/vessels',   icon: '🚢', label: 'Vessels',        section: null },
  { path: '/congestion',icon: '⚡', label: 'Congestion',     section: null },
  { path: '/resources', icon: '🏗️', label: 'Resources',      section: null },
  { path: '/routing',   icon: '🗺️', label: 'Routing',        section: 'PLANNING' },
  { path: '/plan',      icon: '📋', label: '72-Hour Plan',   section: null },
]

export default function Layout({ children, title, subtitle }) {
  const navigate  = useNavigate()
  const location  = useLocation()
  const [apiOk, setApiOk] = useState(null)
  const [lastRefresh, setLastRefresh] = useState('')

  useEffect(() => {
    const check = () =>
      fetchHealth()
        .then(() => { setApiOk(true); setLastRefresh(new Date().toLocaleTimeString()) })
        .catch(() => setApiOk(false))
    check()
    const id = setInterval(check, 30000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="layout">
      {/* Sidebar */}
      <nav className="sidebar">
        <div className="sidebar-brand">
          <h1>🚢 CongestiQ</h1>
          <p>Port Operations Optimizer</p>
        </div>
        <div className="sidebar-nav">
          {NAV.map((item, i) => (
            <React.Fragment key={item.path}>
              {item.section && (
                <div className="nav-section">{item.section}</div>
              )}
              <div
                className={`nav-link ${location.pathname === item.path ? 'active' : ''}`}
                onClick={() => navigate(item.path)}
              >
                <span className="icon">{item.icon}</span>
                <span>{item.label}</span>
              </div>
            </React.Fragment>
          ))}
        </div>
      </nav>

      {/* Main area */}
      <div className="main-area">
        <header className="topbar">
          <div>
            <div className="topbar-title">{title}</div>
            {subtitle && <div className="topbar-subtitle">{subtitle}</div>}
          </div>
          <div className="topbar-spacer" />
          <div className="topbar-status">
            <div className={`status-dot ${apiOk === false ? 'error' : ''}`} />
            {apiOk === true
              ? `API connected · ${lastRefresh}`
              : apiOk === false
              ? 'API unavailable'
              : 'Connecting…'}
          </div>
        </header>

        <main className="page-content">
          {children}
        </main>
      </div>
    </div>
  )
}
