import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { useSharingStore } from '../../store/useSharingStore'
import type { Share, ShareRole } from '../../types'

export function ShareDialog({
  workspaceId,
  resourceType,
  resourceId,
  resourceName,
  onClose,
}: {
  workspaceId: string
  resourceType: 'file' | 'dashboard'
  resourceId: string
  resourceName: string
  onClose: () => void
}) {
  const { listShares, createShare, revokeShare, error } = useSharingStore()
  const [shares, setShares] = useState<Share[]>([])
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<ShareRole>('viewer')
  const [submitting, setSubmitting] = useState(false)

  const refresh = () => {
    listShares(workspaceId, resourceType, resourceId).then(setShares)
  }

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    const ok = await createShare(workspaceId, resourceType, resourceId, email.trim(), role)
    setSubmitting(false)
    if (ok) {
      setEmail('')
      refresh()
    }
  }

  const handleRevoke = async (shareId: string) => {
    await revokeShare(workspaceId, resourceType, resourceId, shareId)
    refresh()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="panel w-full max-w-md p-5" onClick={(e) => e.stopPropagation()}>
        <div className="mb-1 flex items-center justify-between">
          <div className="text-sm font-semibold text-slate-100">Share "{resourceName}"</div>
          <button className="!border-0 !bg-transparent !p-1" onClick={onClose}>
            <X size={15} />
          </button>
        </div>
        <div className="muted mb-4 text-xs">
          Grants access to this {resourceType} to a specific account, even if they aren't a member of this workspace.
        </div>

        <form onSubmit={submit} className="mb-4 flex gap-2">
          <input className="flex-1 !text-xs" type="email" placeholder="Email address" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <select className="!text-xs" value={role} onChange={(e) => setRole(e.target.value as ShareRole)}>
            <option value="viewer">Can view</option>
            {resourceType === 'file' && <option value="editor">Can edit</option>}
          </select>
          <button type="submit" disabled={submitting} className="!border-blue-800 !bg-blue-700 !text-xs hover:!bg-blue-600">
            Share
          </button>
        </form>
        {error && <div className="mb-3 rounded border border-rose-900/50 bg-rose-950/30 px-2 py-1.5 text-xs text-rose-300">{error}</div>}

        <div className="space-y-1">
          {shares.length === 0 && <div className="muted text-xs">Not shared with anyone yet.</div>}
          {shares.map((s) => (
            <div key={s.id} className="flex items-center justify-between rounded px-1 py-1 text-xs">
              <span className="text-slate-300">{s.shared_with_email}</span>
              <div className="flex items-center gap-2">
                <span className="muted uppercase tracking-wide">{s.role}</span>
                <button className="!border-0 !bg-transparent !p-0.5 text-[11px] hover:!text-rose-400" onClick={() => handleRevoke(s.id)}>
                  Revoke
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
