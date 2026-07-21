import { create } from 'zustand'
import api from '../services/api'
import type { ScheduledQuery } from '../types'
import { useAuthStore } from './useAuthStore'

function authHeaders() {
  const token = useAuthStore.getState().token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

type NewScheduleInput = {
  connection_id: string
  name: string
  sql: string
  cron_expression: string
  condition: 'always' | 'threshold' | 'diff'
  condition_value?: number | null
  notify_webhook_url?: string | null
  notify_email?: string | null
}

type ScheduledQueryState = {
  schedules: ScheduledQuery[]
  error: string | null

  loadSchedules: (workspaceId: string) => Promise<void>
  createSchedule: (workspaceId: string, input: NewScheduleInput) => Promise<boolean>
  updateSchedule: (workspaceId: string, id: string, patch: Partial<ScheduledQuery>) => Promise<boolean>
  deleteSchedule: (workspaceId: string, id: string) => Promise<void>
  runNow: (workspaceId: string, id: string) => Promise<void>
}

function errorDetail(err: unknown): string {
  return (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Request failed.'
}

export const useScheduledQueryStore = create<ScheduledQueryState>((set, get) => ({
  schedules: [],
  error: null,

  loadSchedules: async (workspaceId) => {
    const { data } = await api.get(`/workspaces/${workspaceId}/scheduled-queries`, { headers: authHeaders() })
    set({ schedules: data })
  },

  createSchedule: async (workspaceId, input) => {
    set({ error: null })
    try {
      await api.post(`/workspaces/${workspaceId}/scheduled-queries`, input, { headers: authHeaders() })
      await get().loadSchedules(workspaceId)
      return true
    } catch (err) {
      set({ error: errorDetail(err) })
      return false
    }
  },

  updateSchedule: async (workspaceId, id, patch) => {
    set({ error: null })
    try {
      await api.patch(`/workspaces/${workspaceId}/scheduled-queries/${id}`, patch, { headers: authHeaders() })
      await get().loadSchedules(workspaceId)
      return true
    } catch (err) {
      set({ error: errorDetail(err) })
      return false
    }
  },

  deleteSchedule: async (workspaceId, id) => {
    await api.delete(`/workspaces/${workspaceId}/scheduled-queries/${id}`, { headers: authHeaders() })
    set((state) => ({ schedules: state.schedules.filter((s) => s.id !== id) }))
  },

  runNow: async (workspaceId, id) => {
    await api.post(`/workspaces/${workspaceId}/scheduled-queries/${id}/run`, {}, { headers: authHeaders() })
    await get().loadSchedules(workspaceId)
  },
}))
