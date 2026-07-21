import { create } from 'zustand'
import api from '../services/api'
import type { ChartType, Dashboard, DashboardDetail, DashboardItem } from '../types'
import { useAuthStore } from './useAuthStore'

function authHeaders() {
  const token = useAuthStore.getState().token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

type NewItemInput = {
  connection_id: string
  title: string
  sql: string
  chart_type: ChartType
  x_field?: string | null
  y_fields?: string[]
  width?: number
}

type DashboardState = {
  dashboards: Dashboard[]
  currentDashboard: DashboardDetail | null
  loading: boolean
  error: string | null

  loadDashboards: (workspaceId: string) => Promise<void>
  createDashboard: (workspaceId: string, name: string) => Promise<Dashboard>
  loadDashboard: (workspaceId: string, dashboardId: string) => Promise<void>
  deleteDashboard: (workspaceId: string, dashboardId: string) => Promise<void>
  addItem: (workspaceId: string, dashboardId: string, item: NewItemInput) => Promise<DashboardItem | null>
  updateItem: (workspaceId: string, dashboardId: string, itemId: string, patch: Partial<DashboardItem>) => Promise<void>
  deleteItem: (workspaceId: string, dashboardId: string, itemId: string) => Promise<void>
  moveItem: (workspaceId: string, dashboardId: string, itemId: string, direction: 'up' | 'down') => Promise<void>
}

function errorDetail(err: unknown): string {
  return (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Request failed.'
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  dashboards: [],
  currentDashboard: null,
  loading: false,
  error: null,

  loadDashboards: async (workspaceId) => {
    const { data } = await api.get(`/workspaces/${workspaceId}/dashboards`, { headers: authHeaders() })
    set({ dashboards: data })
  },

  createDashboard: async (workspaceId, name) => {
    const { data } = await api.post(`/workspaces/${workspaceId}/dashboards`, { name }, { headers: authHeaders() })
    set((state) => ({ dashboards: [...state.dashboards, data] }))
    return data
  },

  loadDashboard: async (workspaceId, dashboardId) => {
    set({ loading: true, error: null })
    try {
      const { data } = await api.get(`/workspaces/${workspaceId}/dashboards/${dashboardId}`, { headers: authHeaders() })
      set({ currentDashboard: data, loading: false })
    } catch (err) {
      set({ error: errorDetail(err), loading: false })
    }
  },

  deleteDashboard: async (workspaceId, dashboardId) => {
    await api.delete(`/workspaces/${workspaceId}/dashboards/${dashboardId}`, { headers: authHeaders() })
    set((state) => ({ dashboards: state.dashboards.filter((d) => d.id !== dashboardId) }))
  },

  addItem: async (workspaceId, dashboardId, item) => {
    try {
      const { data } = await api.post(`/workspaces/${workspaceId}/dashboards/${dashboardId}/items`, item, { headers: authHeaders() })
      await get().loadDashboard(workspaceId, dashboardId)
      return data
    } catch (err) {
      set({ error: errorDetail(err) })
      return null
    }
  },

  updateItem: async (workspaceId, dashboardId, itemId, patch) => {
    await api.patch(`/workspaces/${workspaceId}/dashboards/${dashboardId}/items/${itemId}`, patch, { headers: authHeaders() })
    await get().loadDashboard(workspaceId, dashboardId)
  },

  deleteItem: async (workspaceId, dashboardId, itemId) => {
    await api.delete(`/workspaces/${workspaceId}/dashboards/${dashboardId}/items/${itemId}`, { headers: authHeaders() })
    await get().loadDashboard(workspaceId, dashboardId)
  },

  moveItem: async (workspaceId, dashboardId, itemId, direction) => {
    const dashboard = get().currentDashboard
    if (!dashboard) return
    const items = [...dashboard.items].sort((a, b) => a.sort_order - b.sort_order)
    const idx = items.findIndex((i) => i.id === itemId)
    const swapWith = direction === 'up' ? idx - 1 : idx + 1
    if (idx === -1 || swapWith < 0 || swapWith >= items.length) return
    const a = items[idx]
    const b = items[swapWith]
    await api.patch(`/workspaces/${workspaceId}/dashboards/${dashboardId}/items/${a.id}`, { sort_order: b.sort_order }, { headers: authHeaders() })
    await api.patch(`/workspaces/${workspaceId}/dashboards/${dashboardId}/items/${b.id}`, { sort_order: a.sort_order }, { headers: authHeaders() })
    await get().loadDashboard(workspaceId, dashboardId)
  },
}))
