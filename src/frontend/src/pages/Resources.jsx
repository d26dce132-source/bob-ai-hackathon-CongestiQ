import React, { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { Badge, Loading, ErrorState, formatEta } from '../components/Shared'
import { fetchAssignments, fetchCraneAssignments } from '../api/client'

function BerthTab({ data }) {
  const changes = data.recommendations.filter(r => r.change_required)
  const ok      = data.recommendations.filter(r => !r.change_required)

  return (
    <div>
      <div className="flex-row mb-4" style={{ flexWrap: 'wrap' }}>
        <span className="badge info">{data.total_recommendations} evaluated</span>
        <span className="badge HIGH">{changes.length} changes recommended</span>
        <span className="badge LOW">{ok.length} optimal</span>
        {data.unassignable_count > 0 && (
          <span className="badge CRITICAL">{data.unassignable_count} unassignable</span>
        )}
      </div>
      <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14 }}>{data.summary}</p>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Vessel</th>
              <th>Type</th>
              <th>ETA</th>
              <th>Current Berth</th>
              <th>Recommended Berth</th>
              <th>Terminal</th>
              <th>Fit Score</th>
              <th>Action</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {data.recommendations.map(r => (
              <tr key={r.schedule_id}>
                <td style={{ fontWeight: 500 }}>{r.vessel_name}</td>
                <td className="td-muted">{r.vessel_type?.replace('_', ' ')}</td>
                <td className="td-muted">{formatEta(r.eta)}</td>
                <td className="td-mono">{r.current_berth_code || '—'}</td>
                <td className="td-mono" style={{ fontWeight: 600 }}>
                  {r.recommended_berth_code}
                </td>
                <td className="td-muted" style={{ fontSize: 11 }}>{r.recommended_terminal}</td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{
                      width: 60, height: 5, borderRadius: 3,
                      background: 'var(--border)', overflow: 'hidden',
                    }}>
                      <div style={{
                        width: `${Math.min(r.fit_score, 100)}%`, height: '100%',
                        background: r.fit_score >= 60 ? 'var(--low)' : r.fit_score >= 30 ? 'var(--medium)' : 'var(--critical)',
                      }} />
                    </div>
                    <span style={{ fontSize: 11 }}>{r.fit_score?.toFixed(0)}</span>
                  </div>
                </td>
                <td>
                  {r.fit_score === 0
                    ? <span className="badge CRITICAL">Unassignable</span>
                    : r.change_required
                    ? <span className="assignment-change">⟳ Change</span>
                    : <span className="assignment-ok">✓ Optimal</span>}
                </td>
                <td style={{ fontSize: 11, color: 'var(--text-muted)', maxWidth: 200 }}>{r.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function CraneTab({ data }) {
  return (
    <div>
      <div className="flex-row mb-4" style={{ flexWrap: 'wrap' }}>
        <span className="badge info">{data.total_recommendations} vessels evaluated</span>
        {data.shortfall_count > 0
          ? <span className="badge CRITICAL">{data.shortfall_count} crane shortfall(s)</span>
          : <span className="badge LOW">No crane shortfalls</span>}
      </div>
      <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14 }}>{data.summary}</p>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Vessel</th>
              <th>Type</th>
              <th>Berth</th>
              <th>ETA</th>
              <th>Required</th>
              <th>Recommended Cranes</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {data.recommendations.map(r => (
              <tr key={r.schedule_id}>
                <td style={{ fontWeight: 500 }}>{r.vessel_name}</td>
                <td className="td-muted">{r.vessel_type?.replace('_', ' ')}</td>
                <td className="td-mono">{r.berth_code || '—'}</td>
                <td className="td-muted">{formatEta(r.eta)}</td>
                <td style={{ textAlign: 'center', fontWeight: 600 }}>{r.cranes_required}</td>
                <td>
                  {r.cranes_recommended.length === 0
                    ? <span style={{ color: 'var(--critical)', fontSize: 12 }}>None available</span>
                    : r.cranes_recommended.map(c => (
                      <span key={c.crane_id} className="badge info" style={{ marginRight: 4, marginBottom: 2, display: 'inline-flex' }}>
                        {c.crane_code}
                      </span>
                    ))
                  }
                </td>
                <td>
                  {r.cranes_shortfall > 0
                    ? <span className="badge CRITICAL">-{r.cranes_shortfall} short</span>
                    : <span className="badge LOW">✓ OK</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.recommendations.some(r => r.shortfall_warning) && (
        <div className="notice-banner mt-4">
          <strong>⚠ Crane Shortfalls Detected</strong>
          {data.recommendations
            .filter(r => r.shortfall_warning)
            .map(r => <div key={r.schedule_id}>• {r.shortfall_warning}</div>)}
        </div>
      )}
    </div>
  )
}

export default function Resources() {
  const [berths, setBerths] = useState(null)
  const [cranes, setCranes] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)
  const [tab, setTab]       = useState('berths')

  const load = () => {
    setLoading(true)
    setError(null)
    Promise.all([fetchAssignments(), fetchCraneAssignments()])
      .then(([b, c]) => {
        setBerths(b.data)
        setCranes(c.data)
        setLoading(false)
      })
      .catch(e => { setError(e.message); setLoading(false) })
  }
  useEffect(load, [])

  if (loading) return <Layout title="Resources"><Loading /></Layout>
  if (error)   return <Layout title="Resources"><ErrorState message={error} onRetry={load} /></Layout>

  return (
    <Layout
      title="Berth & Crane Assignments"
      subtitle="Optimized assignments for the next 72 hours"
    >
      {/* Tab switcher */}
      <div className="flex-row mb-4">
        {['berths', 'cranes'].map(t => (
          <button key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '7px 20px',
              borderRadius: 6,
              border: '1px solid var(--border)',
              background: tab === t ? 'var(--accent)' : 'var(--surface)',
              color: tab === t ? 'white' : 'var(--text)',
              fontWeight: 600, fontSize: 13, cursor: 'pointer',
            }}
          >
            {t === 'berths' ? '🏗️ Berth Assignments' : '🔧 Crane Assignments'}
          </button>
        ))}
      </div>

      <div className="card">
        <div className="card-body">
          {tab === 'berths' && berths && <BerthTab data={berths} />}
          {tab === 'cranes' && cranes && <CraneTab data={cranes} />}
        </div>
      </div>
    </Layout>
  )
}
