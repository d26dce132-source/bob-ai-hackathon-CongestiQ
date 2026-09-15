import React from 'react'

export function Badge({ level }) {
  return <span className={`badge ${level}`}>{level}</span>
}

export function ScoreBar({ score, level }) {
  return (
    <div className="score-bar-wrap">
      <div className="score-bar">
        <div
          className={`score-bar-fill ${level}`}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
      <span className="score-label">{score?.toFixed(0)}</span>
    </div>
  )
}

export function Loading() {
  return (
    <div className="state-box">
      <div className="spinner" />
      <p>Loading data from backend…</p>
    </div>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="state-box">
      <div className="state-icon">⚠️</div>
      <p>{message || 'Could not reach the backend API.'}</p>
      <p className="text-sm">Make sure the FastAPI server is running on port 8000.</p>
      {onRetry && (
        <button className="retry-btn" onClick={onRetry}>Retry</button>
      )}
    </div>
  )
}

export function Card({ title, subtitle, children, action }) {
  return (
    <div className="card mb-4">
      {title && (
        <div className="card-header">
          <div>
            <div className="card-title">{title}</div>
            {subtitle && <div className="card-subtitle">{subtitle}</div>}
          </div>
          {action}
        </div>
      )}
      <div className="card-body">{children}</div>
    </div>
  )
}

export function formatEta(isoStr) {
  if (!isoStr) return '—'
  const d = new Date(isoStr)
  return d.toLocaleString('en-GB', {
    day: '2-digit', month: 'short',
    hour: '2-digit', minute: '2-digit',
    hour12: false,
  }).replace(',', '')
}
