import { useEffect } from 'react'
import { AIPanel } from './components/AIPanel'
import { EditorPanel } from './components/EditorPanel'
import { ResultsPanel } from './components/ResultsPanel'
import { Sidebar } from './components/Sidebar'
import { useStudioStore } from './store/useStudioStore'

export default function App() {
  const loadBoot = useStudioStore((state) => state.loadBoot)
  const backendConnected = useStudioStore((state) => state.backendConnected)
  const bootError = useStudioStore((state) => state.bootError)
  const aiStatus = useStudioStore((state) => state.aiStatus)
  const loading = useStudioStore((state) => state.loading)

  useEffect(() => {
    loadBoot()
  }, [loadBoot])

  const aiColor =
    aiStatus?.status === 'connected' ? 'border-emerald-800 bg-emerald-950/60 text-emerald-300' :
    aiStatus?.status === 'mock' ? 'border-amber-800 bg-amber-950/60 text-amber-300' :
    'border-slate-700 bg-slate-800/60 text-slate-400'

  if (!backendConnected && !loading && bootError) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950">
        <div className="rounded-2xl border border-slate-800 bg-slate-900 p-8 text-center max-w-sm">
          <div className="mb-3 text-2xl">⚠️</div>
          <div className="mb-2 text-lg font-semibold text-slate-100">Backend not running</div>
          <div className="text-sm text-slate-400">{bootError}</div>
          <div className="mt-4 rounded-lg bg-slate-800 p-3 text-left font-mono text-xs text-slate-300">
            cd backend<br />
            uvicorn app.main:app --port 8000
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen overflow-hidden bg-slate-950 p-3 text-slate-100">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-900/80 px-5 py-3 backdrop-blur">
        <div className="flex items-center gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold tracking-tight text-slate-100">AI SQL Studio</span>
              <span className="rounded-full border border-slate-700 bg-slate-800 px-2 py-0.5 text-[10px] text-slate-400">local-first</span>
            </div>
            <div className="text-xs text-slate-500">Natural language → SQL · local AI · privacy preserved</div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {!backendConnected && (
            <div className="rounded-full border border-rose-800 bg-rose-950/60 px-3 py-1 text-xs text-rose-300">
              ⚠ backend offline
            </div>
          )}
          <div className="rounded-full border border-sky-800 bg-sky-950/60 px-3 py-1 text-xs text-sky-300">
            🔒 read-only SQL
          </div>
          <div className={`rounded-full border px-3 py-1 text-xs ${aiColor}`}>
            {loading && !aiStatus ? (
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2 w-2 animate-spin rounded-full border border-slate-500 border-t-slate-300" />
                connecting…
              </span>
            ) : (
              <span>{aiStatus?.provider ?? 'AI'} · {aiStatus?.active_model ?? aiStatus?.status ?? '—'}</span>
            )}
          </div>
        </div>
      </div>

      {/* Main layout */}
      <div className="grid h-[calc(100vh-5.5rem)] grid-cols-12 gap-3">
        <div className="col-span-3 min-h-0"><Sidebar /></div>
        <div className="col-span-6 grid min-h-0 grid-rows-[1.15fr_0.85fr] gap-3">
          <div className="min-h-0 relative"><EditorPanel /></div>
          <div className="min-h-0"><ResultsPanel /></div>
        </div>
        <div className="col-span-3 min-h-0"><AIPanel /></div>
      </div>
    </div>
  )
}
