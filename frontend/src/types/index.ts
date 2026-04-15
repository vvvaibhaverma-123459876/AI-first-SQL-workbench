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

export type QueryResult = {
  columns: string[]
  rows: Record<string, unknown>[]
  row_count: number
  execution_ms: number
  message: string
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
