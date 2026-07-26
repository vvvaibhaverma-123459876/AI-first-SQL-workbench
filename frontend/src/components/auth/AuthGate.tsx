import { useEffect, useState } from 'react'
import { LogOut, Plus } from 'lucide-react'
import { useAuthStore } from '../../store/useAuthStore'

function LoginForm() {
  const { login, register, error } = useAuthStore()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      if (mode === 'login') await login(email, password)
      else await register(email, password, displayName)
    } catch {
      // error is already set in the store; nothing else to do here
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex h-screen items-center justify-center bg-slate-950">
      <form onSubmit={submit} className="panel w-full max-w-sm p-8">
        <div className="mb-1 text-lg font-semibold text-slate-100">AI SQL Studio</div>
        <div className="muted mb-6 text-sm">{mode === 'login' ? 'Sign in to your workspaces.' : 'Create an account to get started.'}</div>

        {mode === 'register' && (
          <label className="mb-3 block text-xs text-slate-400">
            Name
            <input className="mt-1 w-full" value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
          </label>
        )}
        <label className="mb-3 block text-xs text-slate-400">
          Email
          <input type="email" className="mt-1 w-full" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label className="mb-4 block text-xs text-slate-400">
          Password
          <input type="password" className="mt-1 w-full" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
        </label>

        {error && <div className="mb-4 rounded-lg border border-rose-900/50 bg-rose-950/30 px-3 py-2 text-xs text-rose-300">{error}</div>}

        <button type="submit" disabled={submitting} className="w-full !border-blue-800 !bg-blue-700 hover:!bg-blue-600">
          {submitting ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
        </button>

        <button
          type="button"
          className="mt-3 w-full !border-0 !bg-transparent text-slate-400 hover:!bg-transparent hover:text-slate-200"
          onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
        >
          {mode === 'login' ? "Don't have an account? Create one" : 'Already have an account? Sign in'}
        </button>
      </form>
    </div>
  )
}

function WorkspacePicker() {
  const { workspaces, activeWorkspaceId, setActiveWorkspace, createWorkspace, user, logout } = useAuthStore()
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')

  const submitCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    await createWorkspace(name.trim())
    setName('')
    setCreating(false)
  }

  if (activeWorkspaceId && workspaces.some((w) => w.id === activeWorkspaceId)) {
    return null
  }

  return (
    <div className="flex h-screen items-center justify-center bg-slate-950">
      <div className="panel w-full max-w-md p-8">
        <div className="mb-1 flex items-center justify-between">
          <div className="text-lg font-semibold text-slate-100">Workspaces</div>
          <button className="!border-0 !bg-transparent text-slate-500 hover:text-slate-200" onClick={logout} title="Sign out">
            <LogOut size={16} />
          </button>
        </div>
        <div className="muted mb-6 text-sm">Signed in as {user?.email}</div>

        {workspaces.length > 0 && (
          <div className="mb-4 space-y-2">
            {workspaces.map((w) => (
              <button key={w.id} className="w-full !justify-start !bg-slate-800/60 text-left" onClick={() => setActiveWorkspace(w.id)}>
                <span className="font-medium">{w.name}</span>
                <span className="muted ml-2 text-xs uppercase tracking-wide">{w.role}</span>
              </button>
            ))}
          </div>
        )}

        {creating ? (
          <form onSubmit={submitCreate} className="space-y-2">
            <input autoFocus className="w-full" placeholder="Workspace name" value={name} onChange={(e) => setName(e.target.value)} />
            <div className="flex gap-2">
              <button type="submit" className="flex-1 !border-blue-800 !bg-blue-700 hover:!bg-blue-600">Create</button>
              <button type="button" className="flex-1" onClick={() => setCreating(false)}>Cancel</button>
            </div>
          </form>
        ) : (
          <button className="w-full" onClick={() => setCreating(true)}>
            <Plus size={14} className="mr-1 inline" />New workspace
          </button>
        )}
      </div>
    </div>
  )
}

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { status, bootstrap, activeWorkspaceId, workspaces } = useAuthStore()

  useEffect(() => {
    bootstrap()
  }, [bootstrap])

  if (status === 'checking') {
    return <div className="flex h-screen items-center justify-center bg-slate-950 text-slate-500">Loading…</div>
  }
  if (status === 'signed_out') {
    return <LoginForm />
  }
  if (!activeWorkspaceId || !workspaces.some((w) => w.id === activeWorkspaceId)) {
    return <WorkspacePicker />
  }
  return <>{children}</>
}
