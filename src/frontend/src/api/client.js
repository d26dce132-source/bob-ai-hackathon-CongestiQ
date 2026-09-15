/**
 * CongestiQ API client
 * All backend calls flow through this module.
 * Base URL defaults to /api (proxied by Vite dev-server to localhost:8000).
 */
import axios from 'axios'

const BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

const api = axios.create({
  baseURL: BASE,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Phase 1 ──────────────────────────────────────────────────────────────────
export const fetchHealth       = ()       => api.get('/health')
export const fetchVessels      = (params) => api.get('/vessels', { params })
export const fetchBerths       = (params) => api.get('/berths',  { params })
export const fetchCranes       = (params) => api.get('/cranes',  { params })
export const fetchSchedules    = (params) => api.get('/schedules', { params })

// ── Phase 2 ──────────────────────────────────────────────────────────────────
export const fetchCongestion   = ()       => api.get('/congestion')
export const fetchHotspots     = ()       => api.get('/congestion/hotspots')
export const fetchVesselRisks  = (params) => api.get('/vessels/risk', { params })

// ── Phase 3 ──────────────────────────────────────────────────────────────────
export const fetchAssignments       = () => api.get('/assignments')
export const fetchCraneAssignments  = () => api.get('/assignments/cranes')
export const fetchRouting           = () => api.get('/routing/recommendations')
export const fetchOperationsPlan    = () => api.get('/operations-plan')

export default api
