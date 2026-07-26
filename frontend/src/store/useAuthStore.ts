import { create } from 'zustand'
import api from '../services/api'
import type { AuthUser, Workspace } from '../types'

const TOKEN_KEY = 'ai_sql_studio_token'
const WORKSPACE_KEY = 'ai_sql_studio_active_workspace'

type AuthState = {
  token: string | null
  user: AuthUser | null
  workspaces: Workspace[]
  activeWorkspaceId: string | null
  status: 'checking' | 'signed_out' | 'signed_in'
  error: string
  bootstrap: () => Promise<void>
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, displayName: string) => Promise<void>
  logout: () => void
  loadWorkspaces: () => Promise<void>
  createWorkspace: (name: string) => Promise<void>
  setActiveWorkspace: (id: string) => void
}

function authHeader(token: string | null) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem(TOKEN_KEY),
  user: null,
  workspaces: [],
  activeWorkspaceId: localStorage.getItem(WORKSPACE_KEY),
  status: 'checking',
  error: '',

  bootstrap: async () => {
    const token = get().token
    if (!token) {
      set({ status: 'signed_out' })
      return
    }
    try {
      const { data } = await api.get('/users/me', { headers: authHeader(token) })
      set({ user: data, status: 'signed_in' })
      await get().loadWorkspaces()
    } catch {
      localStorage.removeItem(TOKEN_KEY)
      set({ token: null, user: null, status: 'signed_out' })
    }
  },

  login: async (email, password) => {
    set({ error: '' })
    try {
      const form = new URLSearchParams()
      form.set('username', email)
      form.set('password', password)
      const { data } = await api.post('/auth/jwt/login', form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      localStorage.setItem(TOKEN_KEY, data.access_token)
      set({ token: data.access_token, status: 'signed_in' })
      const me = await api.get('/users/me', { headers: authHeader(data.access_token) })
      set({ user: me.data })
      await get().loadWorkspaces()
    } catch (err: any) {
      set({ error: err?.response?.data?.detail ?? 'Login failed.' })
      throw err
    }
  },

  register: async (email, password, displayName) => {
    set({ error: '' })
    try {
      await api.post('/auth/register', { email, password, display_name: displayName })
      await get().login(email, password)
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      set({ error: typeof detail === 'string' ? detail : 'Registration failed.' })
      throw err
    }
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(WORKSPACE_KEY)
    set({ token: null, user: null, workspaces: [], activeWorkspaceId: null, status: 'signed_out' })
  },

  loadWorkspaces: async () => {
    const token = get().token
    const { data } = await api.get('/workspaces', { headers: authHeader(token) })
    set({ workspaces: data })
    const active = get().activeWorkspaceId
    if (!active && data.length > 0) {
      get().setActiveWorkspace(data[0].id)
    }
  },

  createWorkspace: async (name) => {
    const token = get().token
    const { data } = await api.post('/workspaces', { name }, { headers: authHeader(token) })
    set((state) => ({ workspaces: [...state.workspaces, data] }))
    get().setActiveWorkspace(data.id)
  },

  setActiveWorkspace: (id) => {
    localStorage.setItem(WORKSPACE_KEY, id)
    set({ activeWorkspaceId: id })
  },
}))
