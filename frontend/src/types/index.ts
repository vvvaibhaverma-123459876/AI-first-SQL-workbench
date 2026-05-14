export type ColumnSchema = {
  name: string
  data_type: string
  is_primary_key: boolean
  is_foreign_key: boolean
  references?: string | null
}

export type TableSchema = {
  name: string
  columns: ColumnSchema[]
}

export type SchemaResponse = {
  tables: TableSchema[]
}

export type TablePreview = {
  table_name: string
  columns: string[]
  rows: Record<string, unknown>[]
}

export type QueryResult = {
  columns: string[]
  rows: Record<string, unknown>[]
  row_count: number
  execution_ms: number
  message: string
  cached?: boolean
}

export type Health = {
  status: string
  ai_provider: string
  api_prefix: string
  database: string
}

export type AIStatus = {
  provider: string
  status: 'connected' | 'not_configured' | 'error' | 'mock'
  active_model?: string | null
  base_url?: string | null
  available_models: string[]
  message: string
  local_only: boolean
}

export type HistoryItem = {
  id: number
  sql_text: string
  status: string
  row_count: number
  execution_ms: number
  error_message?: string | null
  created_at: string
}

export type SavedQuery = {
  id: number
  name: string
  sql_text: string
  description?: string | null
  created_at: string
}

export type Suggestion = {
  table_name: string
  reason: string
  suggested_columns: string[]
}

export type AssistantStep = {
  name: string
  status: 'success' | 'warning' | 'error' | 'cached' | 'skipped'
  detail: string
}

export type AssistantResponse = {
  status: 'success' | 'error'
  question: string
  sql?: string | null
  result?: QueryResult | null
  explanation?: string | null
  suggestions: Suggestion[]
  join_suggestions: string[]
  next_questions: string[]
  warnings: string[]
  errors: string[]
  steps: AssistantStep[]
  cached: boolean
  memory_id?: number | null
  confidence: number
}

export type AssistantMemoryItem = {
  id: number
  question: string
  sql_text: string
  confidence: number
  use_count: number
  positive_feedback: number
  negative_feedback: number
  updated_at: string
}
