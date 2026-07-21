import { useState } from 'react'
import { LogOut, FolderOpen } from 'lucide-react'
import { useAuthStore } from '../../store/useAuthStore'
import { LegacyDemoWorkbench } from '../LegacyDemoWorkbench'

export function WorkspaceShell() {
  const { user, workspaces, activeWorkspaceId, setActiveWorkspace, logout } = useAuthStore()
  const [showLegacy, setShowLegacy] = useState(false)
  const workspace = workspaces.find((w) => w.id === activeWorkspaceId)

  if (showLegacy) {
    return <LegacyDemoWorkbench onExit={() => setShowLegacy(false)} />
  }

  return (
    <div className="flex h-screen flex-col bg-slate-950 text-slate-100">
      <div className="flex items-center justify-between border-b border-slate-800 px-5 py-3">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold">{workspace?.name ?? 'Workspace'}</span>
          {workspaces.length > 1 && (
            <select
              className="!py-1 !text-xs"
              value={activeWorkspaceId ?? ''}
              onChange={(e) => setActiveWorkspace(e.target.value)}
            >
              {workspaces.map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </select>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-400">
          <span>{user?.email}</span>
          <button className="!border-0 !bg-transparent text-slate-500 hover:text-slate-200" onClick={logout} title="Sign out">
            <LogOut size={15} />
          </button>
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center p-8">
        <div className="panel max-w-lg p-8 text-center">
          <FolderOpen size={28} className="mx-auto mb-4 text-slate-600" />
          <div className="mb-2 text-lg font-semibold text-slate-100">Nothing here yet</div>
          <p className="muted mb-6 text-sm leading-relaxed">
            This workspace is real and persisted, but the file tree, editor, and data connections
            that will actually live here are still being built (Phase 1: files &amp; search, Phase 2: connect
            a real database). For now, you can still use the original single-user demo workbench against
            the bundled sample database.
          </p>
          <button className="!border-blue-800 !bg-blue-700 hover:!bg-blue-600" onClick={() => setShowLegacy(true)}>
            Open legacy demo workbench
          </button>
        </div>
      </div>
    </div>
  )
}
