import { create } from 'zustand'
import api from '../services/api'
import type {
  AIStatus,
  AssistantMemoryItem,
  AssistantResponse,
  Health,
  HistoryItem,
  QueryResult,
  SavedQuery,
  SchemaResponse,
  Suggestion,
  TablePreview,
} from '../types'

type Tab = { id: string; title: string; sql: string }

type StudioState = {
  schema: SchemaResponse | null
  health: Health | null
  aiStatus: AIStatus | null
  backendConnected: boolean
  bootError: string
  history: HistoryItem[]
  savedQueries: SavedQuery[]
  results: QueryResult | null
  tablePreview: TablePreview | null
  assistantResponse: AssistantResponse | null
  assistantMemory: AssistantMemoryItem[]
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
  assistantLoading: boolean
  loadBoot: () => Promise<void>
  refreshAIStatus: () => Promise<void>
  setAiPrompt: (value: string) => void
  setSQL: (value: string) => void
  insertSQL: (snippet: string) => void
  addTab: () => void
  setActiveTab: (id: string) => void
  openSQLInTab: (title: string, sql: string) => void
  previewTable: (tableName: string) => Promise<void>
  runSQL: () => Promise<void>
  validateSQL: () => Promise<void>
  generateSQL: () => Promise<void>
  runAssistant: () => Promise<void>
  explainSQL: () => Promise<void>
  repairSQL: () => Promise<void>
  suggestTables: () => Promise<void>
  sendAssistantFeedback: (positive: boolean) => Promise<void>
  saveCurrentQuery: (name: string) => Promise<void>
  deleteSavedQuery: (id: number) => Promise<void>
  loadHistory: () => Promise<void>
  loadAssistantMemory: () => Promise<void>
  exportCSV: () => Promise<void>
}

const starterSQL = `SELECT u.user_id, u.full_name, COUNT(t.transaction_id) AS txn_count, SUM(t.amount) AS total_amount
FROM users u
LEFT JOIN transactions t ON u.user_id = t.user_id
GROUP BY u.user_id, u.full_name
ORDER BY total_amount DESC
LIMIT 25`

function currentTab(state: StudioState) {
  return state.tabs.find((t) => t.id === state.activeTabId)
}

export const useStudioStore = create<StudioState>((set, get) => ({
  schema: null,
  health: null,
  aiStatus: null,
  backendConnected: false,
  bootError: '',
  history: [],
  savedQueries: [],
  results: null,
  tablePreview: null,
  assistantResponse: null,
  assistantMemory: [],
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
  assistantLoading: false,

  loadBoot: async () => {
    set({ loading: true, bootError: '' })
    try {
      const [health, aiStatus, schema, history, saved, memory] = await Promise.all([
        api.get('/health'),
        api.get('/ai/status'),
        api.get('/schema'),
        api.get('/history'),
        api.get('/saved-queries'),
        api.get('/assistant/memory'),
      ])
      set({
        health: health.data,
        aiStatus: aiStatus.data,
        schema: schema.data,
        history: history.data,
        savedQueries: saved.data,
        assistantMemory: memory.data,
        backendConnected: true,
        loading: false,
        logs: ['Workbench boot completed.', ...get().logs].slice(0, 20),
      })
    } catch (error: any) {
      const message = error?.message ?? 'Backend is not reachable.'
      set({ backendConnected: false, bootError: message, loading: false, logs: [`Boot failed: ${message}`, ...get().logs].slice(0, 20) })
    }
  },

  refreshAIStatus: async () => {
    const { data } = await api.get('/ai/status')
    set({ aiStatus: data })
  },

  setAiPrompt: (value) => set({ aiPrompt: value }),

  setSQL: (value) => set((state) => ({
    tabs: state.tabs.map((tab) => tab.id === state.activeTabId ? { ...tab, sql: value } : tab),
  })),

  insertSQL: (snippet) => set((state) => ({
    tabs: state.tabs.map((tab) => tab.id === state.activeTabId ? { ...tab, sql: `${tab.sql}\n${snippet}` } : tab),
  })),

  addTab: () => set((state) => {
    const nextId = `tab-${Date.now()}`
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

  previewTable: async (tableName) => {
    const { data } = await api.get(`/tables/${tableName}/preview`)
    set({ tablePreview: data })
  },

  validateSQL: async () => {
    const current = currentTab(get())
    if (!current) return
    const { data } = await api.post('/validate-sql', { sql: current.sql })
    set({ validationWarnings: data.warnings ?? [], validationErrors: data.errors ?? [] })
    if (data.normalized_sql) get().setSQL(data.normalized_sql)
  },

  runSQL: async () => {
    const current = currentTab(get())
    if (!current) return
    set({ loading: true, validationErrors: [], validationWarnings: [] })
    try {
      const { data } = await api.post('/execute-sql', { sql: current.sql, use_cache: true })
      set((state) => ({
        results: data,
        logs: [`${data.cached ? 'Cache hit' : 'Executed'} · ${data.row_count} rows · ${data.execution_ms} ms`, ...state.logs].slice(0, 20),
        loading: false,
      }))
      await get().loadHistory()
    } catch (error: any) {
      const message = error?.response?.data?.detail ?? 'Execution failed.'
      set((state) => ({ logs: [message, ...state.logs].slice(0, 20), validationErrors: [message], loading: false }))
    }
  },

  generateSQL: async () => {
    set({ assistantLoading: true })
    try {
      const { data } = await api.post('/generate-sql', { prompt: get().aiPrompt })
      get().setSQL(data.sql)
      const message = data.provider_fallback
        ? `Generated SQL · AI provider fallback: ${data.provider_fallback}`
        : 'Generated SQL from local AI prompt.'
      set((state) => ({ logs: [message, ...state.logs].slice(0, 20), assistantLoading: false }))
    } catch (error: any) {
      set((state) => ({ logs: [`Generation failed: ${error?.message ?? 'unknown error'}`, ...state.logs].slice(0, 20), assistantLoading: false }))
    }
  },

  runAssistant: async () => {
    set({ assistantLoading: true, validationErrors: [], validationWarnings: [] })
    try {
      const { data } = await api.post('/assistant/run', {
        question: get().aiPrompt,
        execute: true,
        explain: true,
        use_cache: true,
      })
      if (data.sql) get().setSQL(data.sql)
      set((state) => ({
        assistantResponse: data,
        results: data.result ?? state.results,
        aiExplanation: data.explanation ?? state.aiExplanation,
        aiSuggestions: data.suggestions ?? [],
        joinSuggestions: data.join_suggestions ?? [],
        validationWarnings: data.warnings ?? [],
        validationErrors: data.errors ?? [],
        logs: [`Assistant ${data.cached ? 'memory hit' : 'run'} · confidence ${Math.round((data.confidence ?? 0) * 100)}%`, ...state.logs].slice(0, 20),
        assistantLoading: false,
      }))
      await get().loadHistory()
      await get().loadAssistantMemory()
    } catch (error: any) {
      set((state) => ({ logs: [`Assistant failed: ${error?.message ?? 'unknown error'}`, ...state.logs].slice(0, 20), assistantLoading: false }))
    }
  },

  explainSQL: async () => {
    const current = currentTab(get())
    if (!current) return
    const { data } = await api.post('/explain-sql', { sql: current.sql })
    set((state) => ({
      aiExplanation: data.explanation,
      logs: data.provider_fallback
        ? [`AI provider fallback: ${data.provider_fallback}`, ...state.logs].slice(0, 20)
        : state.logs,
    }))
  },

  repairSQL: async () => {
    const current = currentTab(get())
    if (!current) return
    const errorMessage = get().validationErrors[0] ?? ''
    const { data } = await api.post('/repair-sql', { sql: current.sql, error_message: errorMessage })
    get().setSQL(data.repaired_sql)
    const message = data.provider_fallback
      ? `${data.rationale} · AI provider fallback: ${data.provider_fallback}`
      : data.rationale ?? 'Repaired SQL using local AI.'
    set((state) => ({ logs: [message, ...state.logs].slice(0, 20) }))
  },

  suggestTables: async () => {
    const { data } = await api.post('/suggest-tables', { prompt: get().aiPrompt })
    set((state) => ({
      aiSuggestions: data.suggestions,
      joinSuggestions: data.join_suggestions,
      logs: data.provider_fallback
        ? [`AI provider fallback: ${data.provider_fallback}`, ...state.logs].slice(0, 20)
        : state.logs,
    }))
  },

  sendAssistantFeedback: async (positive) => {
    const memoryId = get().assistantResponse?.memory_id
    if (!memoryId) return
    await api.post('/assistant/feedback', { memory_id: memoryId, positive })
    await get().loadAssistantMemory()
    set((state) => ({ logs: [`Feedback saved: ${positive ? 'useful' : 'not useful'}.`, ...state.logs].slice(0, 20) }))
  },

  saveCurrentQuery: async (name: string) => {
    const current = currentTab(get())
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

  loadAssistantMemory: async () => {
    const { data } = await api.get('/assistant/memory')
    set({ assistantMemory: data })
  },

  exportCSV: async () => {
    const current = currentTab(get())
    if (!current) return
    const { data } = await api.post('/execute-sql/export', { sql: current.sql, use_cache: false })
    const blob = new Blob([data], { type: 'text/csv;charset=utf-8;' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'query-results.csv'
    link.click()
    window.URL.revokeObjectURL(url)
  },
}))
