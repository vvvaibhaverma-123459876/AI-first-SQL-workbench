import { create } from 'zustand'
import api from '../services/api'
import type { ConnectionQueryResult, ConnectionTableInfo, ConnectorType, DataConnection, TestConnectionResult } from '../types'
import { useAuthStore } from './useAuthStore'

function authHeaders() {
  const token = useAuthStore.getState().token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

type ConnectionState = {
  connections: DataConnection[]
  loadingConnections: boolean
  schemaByConnection: Record<string, ConnectionTableInfo[]>
  queryResult: ConnectionQueryResult | null
  queryError: string | null
  queryRunning: boolean
  // The connection a SQL editor tab's autocomplete resolves against. Set only
  // when the user explicitly picks a connection to run against (QueryRunner) --
  // not when merely browsing another connection's schema tree, so browsing
  // never silently repoints completions for the file being edited.
  activeConnectionId: string | null

  loadConnections: (workspaceId: string) => Promise<void>
  createConnection: (workspaceId: string, name: string, connectorType: ConnectorType, config: Record<string, unknown>) => Promise<void>
  deleteConnection: (workspaceId: string, connectionId: string) => Promise<void>
  testConnection: (workspaceId: string, connectionId: string) => Promise<TestConnectionResult>
  loadSchema: (workspaceId: string, connectionId: string) => Promise<void>
  runQuery: (workspaceId: string, connectionId: string, sql: string) => Promise<void>
  setActiveConnectionId: (workspaceId: string, connectionId: string | null) => void
}

export const useConnectionStore = create<ConnectionState>((set, get) => ({
  connections: [],
  loadingConnections: false,
  schemaByConnection: {},
  queryResult: null,
  queryError: null,
  queryRunning: false,
  activeConnectionId: null,

  loadConnections: async (workspaceId) => {
    set({ loadingConnections: true })
    try {
      const { data } = await api.get(`/workspaces/${workspaceId}/connections`, { headers: authHeaders() })
      set({ connections: data, loadingConnections: false })
    } catch {
      set({ loadingConnections: false })
    }
  },

  createConnection: async (workspaceId, name, connectorType, config) => {
    await api.post(
      `/workspaces/${workspaceId}/connections`,
      { name, config: { connector_type: connectorType, ...config } },
      { headers: authHeaders() },
    )
    const { data } = await api.get(`/workspaces/${workspaceId}/connections`, { headers: authHeaders() })
    set({ connections: data })
  },

  deleteConnection: async (workspaceId, connectionId) => {
    await api.delete(`/workspaces/${workspaceId}/connections/${connectionId}`, { headers: authHeaders() })
    set((state) => ({ connections: state.connections.filter((c) => c.id !== connectionId) }))
  },

  testConnection: async (workspaceId, connectionId) => {
    const { data } = await api.post<TestConnectionResult>(`/workspaces/${workspaceId}/connections/${connectionId}/test`, {}, { headers: authHeaders() })
    const { data: refreshed } = await api.get(`/workspaces/${workspaceId}/connections`, { headers: authHeaders() })
    set({ connections: refreshed })
    return data
  },

  loadSchema: async (workspaceId, connectionId) => {
    const { data } = await api.get(`/workspaces/${workspaceId}/connections/${connectionId}/schema`, { headers: authHeaders() })
    set((state) => ({ schemaByConnection: { ...state.schemaByConnection, [connectionId]: data } }))
  },

  runQuery: async (workspaceId, connectionId, sql) => {
    set({ queryRunning: true, queryError: null })
    try {
      const { data } = await api.post(`/workspaces/${workspaceId}/connections/${connectionId}/query`, { sql }, { headers: authHeaders() })
      set({ queryResult: data, queryRunning: false })
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Query failed.'
      set({ queryError: message, queryResult: null, queryRunning: false })
    }
  },

  setActiveConnectionId: (workspaceId, connectionId) => {
    set({ activeConnectionId: connectionId })
    // Eager-load so autocomplete has schema the moment a connection is
    // selected, not only once a user happens to expand its schema tree.
    if (connectionId && !get().schemaByConnection[connectionId]) {
      void get().loadSchema(workspaceId, connectionId)
    }
  },
}))
