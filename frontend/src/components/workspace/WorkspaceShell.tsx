import { useState } from 'react'
import { LogOut } from 'lucide-react'
import { useAuthStore } from '../../store/useAuthStore'
import { LegacyDemoWorkbench } from '../LegacyDemoWorkbench'
import { IdeShell } from '../ide/IdeShell'

export function WorkspaceShell() {
  const { user, workspaces, activeWorkspaceId, setActiveWorkspace, logout } = useAuthStore()
  const [showLegacy, setShowLegacy] = useState(false)
  const workspace = workspaces.find((w) => w.id === activeWorkspaceId)

  if (showLegacy) {
    return <LegacyDemoWorkbench onExit={() => setShowLegacy(false)} />
  }

  if (!workspace) return null

  return (
    <div className="flex h-screen flex-col bg-slate-950 text-slate-100">
      <div className="flex items-center justify-between border-b border-slate-800 px-5 py-3">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold">{workspace.name}</span>
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
          <button className="!text-xs" onClick={() => setShowLegacy(true)}>Legacy demo workbench</button>
          <span>{user?.email}</span>
          <button className="!border-0 !bg-transparent text-slate-500 hover:text-slate-200" onClick={logout} title="Sign out">
            <LogOut size={15} />
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1">
        <IdeShell workspaceId={workspace.id} onOpenLegacy={() => setShowLegacy(true)} />
      </div>
    </div>
  )
}
