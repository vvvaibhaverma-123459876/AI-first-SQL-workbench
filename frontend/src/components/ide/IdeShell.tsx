import { useEffect, useState } from 'react'
import { FileTree } from './FileTree'
import { EditorTabs } from './EditorTabs'
import { QuickOpen } from './QuickOpen'
import { ContentSearch } from './ContentSearch'
import { CommandPalette, type Command } from './CommandPalette'
import { useFileStore } from '../../store/useFileStore'

export function IdeShell({ workspaceId, onOpenLegacy }: { workspaceId: string; onOpenLegacy: () => void }) {
  const { loadFiles, createFile, activeTabId, saveNow } = useFileStore()
  const [overlay, setOverlay] = useState<'none' | 'quickOpen' | 'search' | 'palette'>('none')

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
      <div className="panel col-span-3 min-h-0 overflow-hidden">
        <FileTree workspaceId={workspaceId} />
      </div>
      <div className="panel col-span-9 min-h-0 overflow-hidden">
        <EditorTabs workspaceId={workspaceId} />
      </div>

      {overlay === 'quickOpen' && <QuickOpen workspaceId={workspaceId} onClose={() => setOverlay('none')} />}
      {overlay === 'search' && <ContentSearch workspaceId={workspaceId} onClose={() => setOverlay('none')} />}
      {overlay === 'palette' && <CommandPalette commands={commands} onClose={() => setOverlay('none')} />}
    </div>
  )
}
