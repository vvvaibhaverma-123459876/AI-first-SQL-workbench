import { useEffect, useState } from 'react'
import { FileTree } from './FileTree'
import { EditorTabs } from './EditorTabs'
import { QuickOpen } from './QuickOpen'
import { ContentSearch } from './ContentSearch'
import { ConnectionsPanel } from './ConnectionsPanel'
import { QueryRunner } from './QueryRunner'
import { InvestigatePanel } from './InvestigatePanel'
import { DashboardsPanel } from './DashboardsPanel'
import { DashboardView } from './DashboardView'
import { CommandPalette, type Command } from './CommandPalette'
import { useFileStore } from '../../store/useFileStore'

export function IdeShell({ workspaceId, onOpenLegacy }: { workspaceId: string; onOpenLegacy: () => void }) {
  const { loadFiles, createFile, activeTabId, openTabs, saveNow } = useFileStore()
  const [overlay, setOverlay] = useState<'none' | 'quickOpen' | 'search' | 'palette'>('none')
  const [sidebarTab, setSidebarTab] = useState<'files' | 'connections' | 'investigate' | 'dashboards'>('files')
  const [openDashboardId, setOpenDashboardId] = useState<string | null>(null)
  const activeTab = openTabs.find((t) => t.fileId === activeTabId)
  const isSqlFile = activeTab?.name.endsWith('.sql') ?? false

  useEffect(() => {
    loadFiles(workspaceId)
  }, [workspaceId, loadFiles])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey
      if (!mod) return
      if (e.key.toLowerCase() === 'p' && e.shiftKey) {
        e.preventDefault()
        setOverlay('palette')
      } else if (e.key.toLowerCase() === 'p') {
        e.preventDefault()
        setOverlay('quickOpen')
      } else if (e.key.toLowerCase() === 'f' && e.shiftKey) {
        e.preventDefault()
        setOverlay('search')
      } else if (e.key.toLowerCase() === 's' && activeTabId) {
        e.preventDefault()
        saveNow(workspaceId, activeTabId)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [activeTabId, workspaceId, saveNow])

  const commands: Command[] = [
    { id: 'new-file', label: 'New File', run: () => { const name = prompt('File name (e.g. query.sql)'); if (name) createFile(workspaceId, { name }) } },
    { id: 'new-folder', label: 'New Folder', run: () => { const name = prompt('Folder name'); if (name) createFile(workspaceId, { name, isFolder: true }) } },
    { id: 'quick-open', label: 'Quick Open File…', run: () => setOverlay('quickOpen') },
    { id: 'search', label: 'Search File Contents…', run: () => setOverlay('search') },
    { id: 'save', label: 'Save Current File', run: () => activeTabId && saveNow(workspaceId, activeTabId) },
    { id: 'legacy', label: 'Open Legacy Demo Workbench', run: onOpenLegacy },
  ]

  return (
    <div className="grid h-full grid-cols-12 gap-3 p-3">
      <div className="panel col-span-3 flex min-h-0 flex-col overflow-hidden">
        <div className="flex border-b border-slate-800">
          <button
            className={`flex-1 !rounded-none !border-0 !border-b-2 !bg-transparent py-1.5 text-xs ${sidebarTab === 'files' ? '!border-b-blue-500 text-slate-100' : '!border-b-transparent text-slate-400'}`}
            onClick={() => setSidebarTab('files')}
          >
            Files
          </button>
          <button
            className={`flex-1 !rounded-none !border-0 !border-b-2 !bg-transparent py-1.5 text-xs ${sidebarTab === 'connections' ? '!border-b-blue-500 text-slate-100' : '!border-b-transparent text-slate-400'}`}
            onClick={() => setSidebarTab('connections')}
          >
            Connections
          </button>
          <button
            className={`flex-1 !rounded-none !border-0 !border-b-2 !bg-transparent py-1.5 text-xs ${sidebarTab === 'investigate' ? '!border-b-blue-500 text-slate-100' : '!border-b-transparent text-slate-400'}`}
            onClick={() => setSidebarTab('investigate')}
          >
            Investigate
          </button>
          <button
            className={`flex-1 !rounded-none !border-0 !border-b-2 !bg-transparent py-1.5 text-xs ${sidebarTab === 'dashboards' ? '!border-b-blue-500 text-slate-100' : '!border-b-transparent text-slate-400'}`}
            onClick={() => setSidebarTab('dashboards')}
          >
            Dashboards
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-hidden">
          {sidebarTab === 'files' && <FileTree workspaceId={workspaceId} />}
          {sidebarTab === 'connections' && <ConnectionsPanel workspaceId={workspaceId} />}
          {sidebarTab === 'investigate' && <InvestigatePanel workspaceId={workspaceId} />}
          {sidebarTab === 'dashboards' && (
            <DashboardsPanel
              workspaceId={workspaceId}
              onOpen={(id) => {
                setOpenDashboardId(id)
              }}
            />
          )}
        </div>
      </div>
      <div className="col-span-9 flex min-h-0 flex-col gap-3">
        {openDashboardId ? (
          <div className="panel min-h-0 flex-1 overflow-hidden">
            <div className="flex items-center justify-between border-b border-slate-800 px-3 py-1.5">
              <span className="muted text-xs">Dashboard view</span>
              <button className="!py-0.5 !text-xs" onClick={() => setOpenDashboardId(null)}>
                Back to files
              </button>
            </div>
            <div className="h-[calc(100%-2rem)]">
              <DashboardView workspaceId={workspaceId} dashboardId={openDashboardId} />
            </div>
          </div>
        ) : (
          <>
            <div className={`panel min-h-0 overflow-hidden ${isSqlFile ? 'flex-[2]' : 'flex-1'}`}>
              <EditorTabs workspaceId={workspaceId} />
            </div>
            {isSqlFile && (
              <div className="panel min-h-0 flex-1 overflow-hidden">
                <QueryRunner workspaceId={workspaceId} sql={activeTab?.content ?? ''} />
              </div>
            )}
          </>
        )}
      </div>

      {overlay === 'quickOpen' && <QuickOpen workspaceId={workspaceId} onClose={() => setOverlay('none')} />}
      {overlay === 'search' && <ContentSearch workspaceId={workspaceId} onClose={() => setOverlay('none')} />}
      {overlay === 'palette' && <CommandPalette commands={commands} onClose={() => setOverlay('none')} />}
    </div>
  )
}
