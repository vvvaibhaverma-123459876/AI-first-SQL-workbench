import { useEffect, useMemo, useState } from 'react'
import { Download, Pin, Play } from 'lucide-react'
import { useConnectionStore } from '../../store/useConnectionStore'
import { useDashboardStore } from '../../store/useDashboardStore'
import type { ChartType } from '../../types'
import { suggestChart } from '../../utils/chartSuggestion'
import { ChartView } from './ChartView'

const CHART_TYPES: ChartType[] = ['table', 'bar', 'line', 'pie', 'scatter']

function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.URL.revokeObjectURL(url)
}

function toCSV(columns: string[], rows: Record<string, unknown>[]): string {
  const escape = (v: unknown) => {
    const s = String(v ?? '')
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  return [columns.join(','), ...rows.map((r) => columns.map((c) => escape(r[c])).join(','))].join('\n')
}

export function QueryRunner({ workspaceId, sql }: { workspaceId: string; sql: string }) {
  const { connections, loadConnections, runQuery, queryResult, queryError, queryRunning } = useConnectionStore()
  const { dashboards, loadDashboards, createDashboard, addItem } = useDashboardStore()
  const [connectionId, setConnectionId] = useState<string>('')
  const [chartType, setChartType] = useState<ChartType>('table')
  const [showPinMenu, setShowPinMenu] = useState(false)
  const [pinTarget, setPinTarget] = useState<'existing' | 'new'>('existing')
  const [pinDashboardId, setPinDashboardId] = useState('')
  const [pinNewName, setPinNewName] = useState('')
  const [pinTitle, setPinTitle] = useState('')
  const [pinError, setPinError] = useState<string | null>(null)
  const [pinning, setPinning] = useState(false)

  useEffect(() => {
    loadConnections(workspaceId)
  }, [workspaceId, loadConnections])

  useEffect(() => {
    if (!connectionId && connections.length > 0) setConnectionId(connections[0].id)
  }, [connections, connectionId])

  const suggestion = useMemo(() => {
    if (!queryResult) return null
    return suggestChart(queryResult.columns, queryResult.rows)
  }, [queryResult])

  useEffect(() => {
    if (suggestion) setChartType(suggestion.chartType)
  }, [suggestion])

  const run = () => {
    if (!connectionId || !sql.trim()) return
    runQuery(workspaceId, connectionId, sql)
  }

  const openPinMenu = () => {
    loadDashboards(workspaceId)
    setPinTitle(sql.trim().slice(0, 60) || 'Untitled tile')
    setShowPinMenu(true)
  }

  const submitPin = async () => {
    if (!queryResult || !connectionId) return
    setPinning(true)
    setPinError(null)
    try {
      let dashboardId = pinDashboardId
      if (pinTarget === 'new') {
        if (!pinNewName.trim()) {
          setPinError('Enter a dashboard name.')
          setPinning(false)
          return
        }
        const created = await createDashboard(workspaceId, pinNewName.trim())
        dashboardId = created.id
      }
      if (!dashboardId) {
        setPinError('Pick a dashboard.')
        setPinning(false)
        return
      }
      const created = await addItem(workspaceId, dashboardId, {
        connection_id: connectionId,
        title: pinTitle.trim() || 'Untitled tile',
        sql,
        chart_type: chartType,
        x_field: suggestion?.xField ?? null,
        y_fields: suggestion?.yFields ?? [],
      })
      if (!created) {
        setPinError(useDashboardStore.getState().error)
        return
      }
      setShowPinMenu(false)
    } finally {
      setPinning(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-800 px-2 py-1.5">
        <select className="w-40 !py-1 !text-xs" value={connectionId} onChange={(e) => setConnectionId(e.target.value)}>
          {connections.length === 0 && <option value="">No connections</option>}
          {connections.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <button
          className="flex items-center gap-1 !border-blue-800 !bg-blue-700 !py-1 !text-xs hover:!bg-blue-600"
          onClick={run}
          disabled={!connectionId || queryRunning}
          title="Run query"
        >
          <Play size={11} />
          {queryRunning ? 'Running…' : 'Run'}
        </button>
        {queryResult && (
          <>
            <span className="muted text-[11px]">
              {queryResult.row_count} row{queryResult.row_count === 1 ? '' : 's'}
              {queryResult.truncated ? ' (truncated)' : ''} in {queryResult.execution_ms}ms
            </span>
            <div className="ml-auto flex items-center gap-1">
              {CHART_TYPES.map((t) => (
                <button key={t} className={`!py-0.5 !text-[11px] ${chartType === t ? '!border-blue-700 !bg-blue-800' : ''}`} onClick={() => setChartType(t)}>
                  {t}
                </button>
              ))}
              <button className="flex items-center gap-1 !py-0.5 !text-[11px]" title="Export CSV" onClick={() => downloadBlob(toCSV(queryResult.columns, queryResult.rows), 'results.csv', 'text/csv;charset=utf-8;')}>
                <Download size={11} />
                CSV
              </button>
              <button className="flex items-center gap-1 !py-0.5 !text-[11px]" title="Export JSON" onClick={() => downloadBlob(JSON.stringify(queryResult.rows, null, 2), 'results.json', 'application/json')}>
                <Download size={11} />
                JSON
              </button>
              <button className="flex items-center gap-1 !py-0.5 !text-[11px]" title="Pin to dashboard" onClick={openPinMenu} disabled={pinning}>
                <Pin size={11} />
                Pin
              </button>
            </div>
          </>
        )}
      </div>

      {showPinMenu && queryResult && (
        <div className="border-b border-slate-800 bg-slate-900/60 p-2">
          <div className="mb-2 flex items-center gap-2">
            <input className="flex-1 !py-1 !text-xs" placeholder="Tile title" value={pinTitle} onChange={(e) => setPinTitle(e.target.value)} />
          </div>
          <div className="mb-2 flex items-center gap-2 text-xs">
            <label className="flex items-center gap-1">
              <input type="radio" checked={pinTarget === 'existing'} onChange={() => setPinTarget('existing')} />
              Existing dashboard
            </label>
            <select className="!py-1 !text-xs" disabled={pinTarget !== 'existing'} value={pinDashboardId} onChange={(e) => setPinDashboardId(e.target.value)}>
              <option value="">Select…</option>
              {dashboards.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-1">
              <input type="radio" checked={pinTarget === 'new'} onChange={() => setPinTarget('new')} />
              New dashboard
            </label>
            <input className="!py-1 !text-xs" placeholder="Dashboard name" disabled={pinTarget !== 'new'} value={pinNewName} onChange={(e) => setPinNewName(e.target.value)} />
          </div>
          {pinError && <div className="mb-2 rounded border border-rose-900/50 bg-rose-950/30 px-2 py-1 text-[11px] text-rose-300">{pinError}</div>}
          <div className="flex gap-2">
            <button className="!border-blue-800 !bg-blue-700 !py-1 !text-xs hover:!bg-blue-600" onClick={submitPin} disabled={pinning}>
              {pinning ? 'Pinning…' : 'Pin to dashboard'}
            </button>
            <button className="!py-1 !text-xs" onClick={() => setShowPinMenu(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-auto p-2">
        {queryError && <div className="m-2 rounded border border-rose-900/50 bg-rose-950/30 px-3 py-2 text-xs text-rose-300">{queryError}</div>}
        {queryResult && <ChartView chartType={chartType} columns={queryResult.columns} rows={queryResult.rows} xField={suggestion?.xField ?? null} yFields={suggestion?.yFields ?? []} />}
        {!queryError && !queryResult && <div className="muted p-3 text-xs">Pick a connection and press Run to execute this file against it.</div>}
      </div>
    </div>
  )
}
