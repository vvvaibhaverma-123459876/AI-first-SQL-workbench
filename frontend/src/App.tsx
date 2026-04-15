import { useEffect } from 'react'
import { AIPanel } from './components/AIPanel'
import { EditorPanel } from './components/EditorPanel'
import { ResultsPanel } from './components/ResultsPanel'
import { Sidebar } from './components/Sidebar'
import { useStudioStore } from './store/useStudioStore'

export default function App() {
  const loadBoot = useStudioStore((state) => state.loadBoot)

  useEffect(() => {
    loadBoot()
  }, [loadBoot])

  return (
    <div className="h-screen overflow-hidden bg-slate-950 p-4 text-slate-100">
      <div className="mb-4 flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-900 px-5 py-4">
        <div>
          <div className="text-xl font-semibold">AI SQL Studio</div>
          <div className="muted text-sm">Local-first AI SQL workbench</div>
        </div>
        <div className="rounded-full border border-emerald-800 bg-emerald-950 px-3 py-1 text-xs text-emerald-300">Read-only safety mode</div>
      </div>

      <div className="grid h-[calc(100vh-6.5rem)] grid-cols-12 gap-4">
        <div className="col-span-3 min-h-0"><Sidebar /></div>
        <div className="col-span-6 grid min-h-0 grid-rows-[1.1fr_0.9fr] gap-4">
          <div className="min-h-0"><EditorPanel /></div>
          <div className="min-h-0"><ResultsPanel /></div>
        </div>
        <div className="col-span-3 min-h-0"><AIPanel /></div>
      </div>
    </div>
  )
}
