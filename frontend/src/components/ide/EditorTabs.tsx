import Editor from '@monaco-editor/react'
import { X } from 'lucide-react'
import { useFileStore } from '../../store/useFileStore'

function languageFor(name: string): string {
  if (name.endsWith('.sql')) return 'sql'
  if (name.endsWith('.md')) return 'markdown'
  if (name.endsWith('.json')) return 'json'
  return 'plaintext'
}

function StatusDot({ status }: { status: string }) {
  const color =
    status === 'saved' ? 'bg-emerald-500' :
    status === 'saving' ? 'bg-amber-400 animate-pulse' :
    status === 'error' ? 'bg-rose-500' :
    'bg-slate-500'
  const label = status === 'saved' ? 'Saved' : status === 'saving' ? 'Saving…' : status === 'error' ? 'Save failed' : 'Unsaved changes'
  return (
    <span className="flex items-center gap-1 text-[10px] text-slate-500" title={label}>
      <span className={`h-1.5 w-1.5 rounded-full ${color}`} />
    </span>
  )
}

export function EditorTabs({ workspaceId }: { workspaceId: string }) {
  const { openTabs, activeTabId, setActiveTab, closeTab, updateContent, saveNow } = useFileStore()
  const active = openTabs.find((t) => t.fileId === activeTabId)

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-0.5 overflow-x-auto border-b border-slate-800 px-2">
        {openTabs.map((tab) => (
          <button
            key={tab.fileId}
            onClick={() => setActiveTab(tab.fileId)}
            className={`!rounded-none !border-0 !border-b-2 flex items-center gap-2 !bg-transparent px-3 py-2 text-xs ${
              tab.fileId === activeTabId ? '!border-b-blue-500 text-slate-100' : '!border-b-transparent text-slate-400'
            }`}
          >
            <StatusDot status={tab.status} />
            <span>{tab.name}</span>
            <span
              role="button"
              className="rounded p-0.5 hover:bg-slate-700"
              onClick={(e) => {
                e.stopPropagation()
                closeTab(tab.fileId)
              }}
            >
              <X size={11} />
            </span>
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1">
        {active ? (
          <Editor
            key={active.fileId}
            language={languageFor(active.name)}
            theme="vs-dark"
            value={active.content}
            onChange={(value) => updateContent(workspaceId, active.fileId, value ?? '')}
            onMount={(editor, monaco) => {
              editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => saveNow(workspaceId, active.fileId))
            }}
            options={{ fontSize: 13, minimap: { enabled: false }, automaticLayout: true }}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-slate-600">
            Open a file from the tree, or press <kbd className="mx-1 rounded bg-slate-800 px-1.5 py-0.5 text-xs">⌘P</kbd> to quick-open.
          </div>
        )}
      </div>
    </div>
  )
}
