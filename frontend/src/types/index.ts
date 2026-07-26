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
  app_version: string
  ai_provider: string
  ai_mode: string
  api_prefix: string
  database: string
  db_row_counts: Record<string, number>
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

export type AuthUser = {
  id: string
  email: string
  display_name: string
  is_active: boolean
  is_superuser: boolean
  is_verified: boolean
}

export type Workspace = {
  id: string
  name: string
  role: 'owner' | 'editor' | 'viewer'
  created_at: string
}

export type FileNode = {
  id: string
  parent_id: string | null
  name: string
  is_folder: boolean
  updated_at: string
}

export type FileDetail = FileNode & {
  content: string
}

export type FileRevision = {
  id: string
  content: string
  created_at: string
}

export type FileSearchResult = {
  file_id: string
  name: string
  snippet: string
}

export type ConnectorType = 'postgres' | 'mysql' | 'sqlite' | 'snowflake' | 'bigquery' | 'databricks'

export type DataConnection = {
  id: string
  name: string
  connector_type: ConnectorType
  created_at: string
  last_tested_at: string | null
  last_test_ok: boolean | null
}

export type ConnectionColumnInfo = {
  name: string
  type: string
  nullable: boolean
}

export type ConnectionTableInfo = {
  schema_name: string | null
  name: string
  columns: ConnectionColumnInfo[]
}

export type ConnectionQueryResult = {
  columns: string[]
  rows: Record<string, unknown>[]
  row_count: number
  truncated: boolean
  execution_ms: number
}

export type TestConnectionResult = {
  ok: boolean
  message: string
}

export type AiJobStatus = 'queued' | 'running' | 'done' | 'failed'

export type AiJob = {
  id: string
  task_type: string
  status: AiJobStatus
  result: Record<string, unknown> | null
  error: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export type ChartType = 'table' | 'bar' | 'line' | 'pie' | 'scatter'

export type Dashboard = {
  id: string
  name: string
  created_at: string
  updated_at: string
}

export type DashboardItem = {
  id: string
  dashboard_id: string
  connection_id: string
  title: string
  sql: string
  chart_type: ChartType
  x_field: string | null
  y_fields: string[]
  width: number
  sort_order: number
  created_at: string
}

export type DashboardDetail = Dashboard & {
  items: DashboardItem[]
}

export type ScheduleCondition = 'always' | 'threshold' | 'diff'

export type ScheduledQuery = {
  id: string
  connection_id: string
  name: string
  sql: string
  cron_expression: string
  condition: ScheduleCondition
  condition_value: number | null
  notify_webhook_url: string | null
  notify_email: string | null
  is_active: boolean
  last_enqueued_at: string | null
  last_run_at: string | null
  last_status: string | null
  last_row_count: number | null
  last_notified_at: string | null
  created_at: string
}

export type ShareRole = 'viewer' | 'editor'

export type Share = {
  id: string
  shared_with_email: string
  role: ShareRole
  created_at: string
}

export type SharedResourceSummary = {
  share_id: string
  resource_type: 'file' | 'dashboard'
  resource_id: string
  resource_name: string
  workspace_id: string
  role: ShareRole
  created_at: string
}

export type SharedFile = {
  id: string
  name: string
  content: string
  role: ShareRole
}

export type SharedDashboardItem = {
  id: string
  title: string
  sql: string
  chart_type: ChartType
  x_field: string | null
  y_fields: string[]
  width: number
  sort_order: number
}

export type SharedDashboard = {
  id: string
  name: string
  role: ShareRole
  items: SharedDashboardItem[]
}

export type FavoriteResourceType = 'file' | 'dashboard'

export type FavoriteSummary = {
  favorite_id: string
  resource_type: FavoriteResourceType
  resource_id: string
  resource_name: string
  created_at: string
}
