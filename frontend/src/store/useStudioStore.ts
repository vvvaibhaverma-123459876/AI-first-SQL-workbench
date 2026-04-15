import { create } from 'zustand'
import api from '../services/api'
import type { HistoryItem, QueryResult, SavedQuery, SchemaResponse, Suggestion } from '../types'

type Tab = { id: string; title: string; sql: string }

type StudioState = {
  schema: SchemaResponse | null
  history: HistoryItem[]
  savedQueries: SavedQuery[]
  results: QueryResult | null
  activeTabId: string
  tabs: Tab[]
  aiExplanation: string
  aiSuggestions: Suggestion[]
  joinSuggestions: string[]
  aiPrompt: string
  logs: string[]
  validationWarnings: string[]
  validationErrors: string[]
  loading: boolean
  loadBoot: () => Promise<void>
  setAiPrompt: (value: string) => void
  setSQL: (value: string) => void
  addTab: () => void
  setActiveTab: (id: string) => void
  openSQLInTab: (title: string, sql: string) => void
  runSQL: () => Promise<void>
  validateSQL: () => Promise<void>
  generateSQL: () => Promise<void>
  explainSQL: () => Promise<void>
  repairSQL: () => Promise<void>
  suggestTables: () => Promise<void>
  saveCurrentQuery: (name: string) => Promise<void>
  deleteSavedQuery: (id: number) => Promise<void>
  loadHistory: () => Promise<void>
  exportCSV: () => Promise<void>
}

const starterSQL = `SELECT u.user_id, u.full_name, COUNT(t.transaction_id) AS txn_count, SUM(t.amount) AS total_amount
FROM users u
LEFT JOIN transactions t ON u.user_id = t.user_id
GROUP BY u.user_id, u.full_name
ORDER BY total_amount DESC
LIMIT 25`

export const useStudioStore = create<StudioState>((set, get) => ({
  schema: null,
  history: [],
  savedQueries: [],
  results: null,
  activeTabId: 'tab-1',
  tabs: [{ id: 'tab-1', title: 'Query 1', sql: starterSQL }],
  aiExplanation: '',
  aiSuggestions: [],
  joinSuggestions: [],
  aiPrompt: 'Show the top 20 users by total transaction amount',
  logs: [],
  validationWarnings: [],
  validationErrors: [],
  loading: false,

  loadBoot: async () => {
    const [schema, history, saved] = await Promise.all([
      api.get('/schema'),
      api.get('/history'),
      api.get('/saved-queries'),
    ])
    set({ schema: schema.data, history: history.data, savedQueries: saved.data })
  },

  setAiPrompt: (value) => set({ aiPrompt: value }),

  setSQL: (value) => set((state) => ({
    tabs: state.tabs.map((tab) => tab.id === state.activeTabId ? { ...tab, sql: value } : tab),
  })),

  addTab: () => set((state) => {
    const nextId = `tab-${state.tabs.length + 1}`
    return {
      tabs: [...state.tabs, { id: nextId, title: `Query ${state.tabs.length + 1}`, sql: 'SELECT * FROM users LIMIT 20' }],
      activeTabId: nextId,
    }
  }),

  setActiveTab: (id) => set({ activeTabId: id }),

  openSQLInTab: (title, sql) => set((state) => {
    const id = `tab-${Date.now()}`
    return { tabs: [...state.tabs, { id, title, sql }], activeTabId: id }
  }),

  validateSQL: async () => {
    const current = get().tabs.find((t) => t.id === get().activeTabId)
    if (!current) return
    const { data } = await api.post('/validate-sql', { sql: current.sql })
    set({ validationWarnings: data.warnings ?? [], validationErrors: data.errors ?? [] })
    if (data.normalized_sql) get().setSQL(data.normalized_sql)
  },

  runSQL: async () => {
    const current = get().tabs.find((t) => t.id === get().activeTabId)
    if (!current) return
    set({ loading: true })
    try {
      const { data } = await api.post('/execute-sql', { sql: current.sql })
      set((state) => ({ results: data, logs: [`Executed in ${data.execution_ms} ms`, ...state.logs].slice(0, 20), loading: false }))
      await get().loadHistory()
    } catch (error: any) {
      const message = error?.response?.data?.detail ?? 'Execution failed.'
      set((state) => ({ logs: [message, ...state.logs].slice(0, 20), validationErrors: [message], loading: false }))
    }
  },

  generateSQL: async () => {
    const { data } = await api.post('/generate-sql', { prompt: get().aiPrompt })
    get().setSQL(data.sql)
    set((state) => ({ logs: ['Generated SQL from prompt.', ...state.logs].slice(0, 20) }))
  },

  explainSQL: async () => {
    const current = get().tabs.find((t) => t.id === get().activeTabId)
    if (!current) return
    const { data } = await api.post('/explain-sql', { sql: current.sql })
    set({ aiExplanation: data.explanation })
  },

  repairSQL: async () => {
    const current = get().tabs.find((t) => t.id === get().activeTabId)
    if (!current) return
    const errorMessage = get().validationErrors[0] ?? ''
    const { data } = await api.post('/repair-sql', { sql: current.sql, error_message: errorMessage })
    get().setSQL(data.repaired_sql)
    set((state) => ({ logs: ['Repaired SQL using AI.', ...state.logs].slice(0, 20) }))
  },

  suggestTables: async () => {
    const { data } = await api.post('/suggest-tables', { prompt: get().aiPrompt })
    set({ aiSuggestions: data.suggestions, joinSuggestions: data.join_suggestions })
  },

  saveCurrentQuery: async (name: string) => {
    const current = get().tabs.find((t) => t.id === get().activeTabId)
    if (!current) return
    await api.post('/saved-queries', { name, sql_text: current.sql, description: 'Saved from UI' })
    const saved = await api.get('/saved-queries')
    set({ savedQueries: saved.data })
  },

  deleteSavedQuery: async (id: number) => {
    await api.delete(`/saved-queries/${id}`)
    const saved = await api.get('/saved-queries')
    set({ savedQueries: saved.data })
  },

  loadHistory: async () => {
    const { data } = await api.get('/history')
    set({ history: data })
  },

  exportCSV: async () => {
    const current = get().tabs.find((t) => t.id === get().activeTabId)
    if (!current) return
    const { data } = await api.post('/execute-sql/export', { sql: current.sql })
    const blob = new Blob([data], { type: 'text/csv;charset=utf-8;' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'query-results.csv'
    link.click()
    window.URL.revokeObjectURL(url)
  },
}))
