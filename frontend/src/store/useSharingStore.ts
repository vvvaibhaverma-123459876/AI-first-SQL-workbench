import { create } from 'zustand'
import api from '../services/api'
import type { Share, SharedDashboard, SharedFile, SharedResourceSummary, ShareRole } from '../types'
import { useAuthStore } from './useAuthStore'

function authHeaders() {
  const token = useAuthStore.getState().token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

type SharingState = {
  sharedWithMe: SharedResourceSummary[]
  activeShare: SharedResourceSummary | null
  activeFile: SharedFile | null
  activeDashboard: SharedDashboard | null
  error: string | null

  loadSharedWithMe: () => Promise<void>
  openShared: (summary: SharedResourceSummary) => Promise<void>
  closeShared: () => void
  updateSharedFileContent: (content: string) => Promise<void>

  listShares: (workspaceId: string, resourceType: 'file' | 'dashboard', resourceId: string) => Promise<Share[]>
  createShare: (workspaceId: string, resourceType: 'file' | 'dashboard', resourceId: string, email: string, role: ShareRole) => Promise<boolean>
  revokeShare: (workspaceId: string, resourceType: 'file' | 'dashboard', resourceId: string, shareId: string) => Promise<void>
}

function errorDetail(err: unknown): string {
  return (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Request failed.'
}

export const useSharingStore = create<SharingState>((set, get) => ({
  sharedWithMe: [],
  activeShare: null,
  activeFile: null,
  activeDashboard: null,
  error: null,

  loadSharedWithMe: async () => {
    const { data } = await api.get('/shared-with-me', { headers: authHeaders() })
    set({ sharedWithMe: data })
  },

  openShared: async (summary) => {
    set({ activeShare: summary, activeFile: null, activeDashboard: null, error: null })
    try {
      if (summary.resource_type === 'file') {
        const { data } = await api.get(`/shared/files/${summary.resource_id}`, { headers: authHeaders() })
        set({ activeFile: data })
      } else {
        const { data } = await api.get(`/shared/dashboards/${summary.resource_id}`, { headers: authHeaders() })
        set({ activeDashboard: data })
      }
    } catch (err) {
      set({ error: errorDetail(err) })
    }
  },

  closeShared: () => set({ activeShare: null, activeFile: null, activeDashboard: null, error: null }),

  updateSharedFileContent: async (content) => {
    const file = get().activeFile
    if (!file) return
    const { data } = await api.patch(`/shared/files/${file.id}`, { content }, { headers: authHeaders() })
    set({ activeFile: data })
  },

  listShares: async (workspaceId, resourceType, resourceId) => {
    const plural = resourceType === 'file' ? 'files' : 'dashboards'
    const { data } = await api.get(`/workspaces/${workspaceId}/${plural}/${resourceId}/shares`, { headers: authHeaders() })
    return data
  },

  createShare: async (workspaceId, resourceType, resourceId, email, role) => {
    set({ error: null })
    const plural = resourceType === 'file' ? 'files' : 'dashboards'
    try {
      await api.post(`/workspaces/${workspaceId}/${plural}/${resourceId}/shares`, { email, role }, { headers: authHeaders() })
      return true
    } catch (err) {
      set({ error: errorDetail(err) })
      return false
    }
  },

  revokeShare: async (workspaceId, resourceType, resourceId, shareId) => {
    const plural = resourceType === 'file' ? 'files' : 'dashboards'
    await api.delete(`/workspaces/${workspaceId}/${plural}/${resourceId}/shares/${shareId}`, { headers: authHeaders() })
  },
}))
