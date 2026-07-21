import { create } from 'zustand'
import api from '../services/api'
import type { FileNode, FileSearchResult } from '../types'
import { useAuthStore } from './useAuthStore'

const AUTOSAVE_DEBOUNCE_MS = 800

export type SaveStatus = 'saved' | 'saving' | 'unsaved' | 'error'

export type OpenTab = {
  fileId: string
  name: string
  content: string
  savedContent: string
  status: SaveStatus
}

type FileState = {
  files: FileNode[]
  openTabs: OpenTab[]
  activeTabId: string | null
  loadingFiles: boolean

  loadFiles: (workspaceId: string) => Promise<void>
  openFile: (workspaceId: string, fileId: string) => Promise<void>
  closeTab: (fileId: string) => void
  setActiveTab: (fileId: string) => void
  updateContent: (workspaceId: string, fileId: string, content: string) => void
  saveNow: (workspaceId: string, fileId: string) => Promise<void>
  createFile: (workspaceId: string, opts: { name: string; parentId?: string | null; isFolder?: boolean; content?: string }) => Promise<FileNode>
  renameFile: (workspaceId: string, fileId: string, name: string) => Promise<void>
  deleteFile: (workspaceId: string, fileId: string) => Promise<void>
  searchContent: (workspaceId: string, query: string) => Promise<FileSearchResult[]>
}

const saveTimers = new Map<string, ReturnType<typeof setTimeout>>()

function authHeaders() {
  const token = useAuthStore.getState().token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export const useFileStore = create<FileState>((set, get) => ({
  files: [],
  openTabs: [],
  activeTabId: null,
  loadingFiles: false,

  loadFiles: async (workspaceId) => {
    set({ loadingFiles: true })
    try {
      const { data } = await api.get(`/workspaces/${workspaceId}/files`, { headers: authHeaders() })
      set({ files: data, loadingFiles: false })
    } catch {
      set({ loadingFiles: false })
    }
  },

  openFile: async (workspaceId, fileId) => {
    const existing = get().openTabs.find((t) => t.fileId === fileId)
    if (existing) {
      set({ activeTabId: fileId })
      return
    }
    const { data } = await api.get(`/workspaces/${workspaceId}/files/${fileId}`, { headers: authHeaders() })
    set((state) => ({
      openTabs: [...state.openTabs, { fileId, name: data.name, content: data.content, savedContent: data.content, status: 'saved' }],
      activeTabId: fileId,
    }))
  },

  closeTab: (fileId) => {
    const timer = saveTimers.get(fileId)
    if (timer) clearTimeout(timer)
    set((state) => {
      const openTabs = state.openTabs.filter((t) => t.fileId !== fileId)
      const activeTabId = state.activeTabId === fileId ? (openTabs[openTabs.length - 1]?.fileId ?? null) : state.activeTabId
      return { openTabs, activeTabId }
    })
  },

  setActiveTab: (fileId) => set({ activeTabId: fileId }),

  updateContent: (workspaceId, fileId, content) => {
    set((state) => ({
      openTabs: state.openTabs.map((t) => (t.fileId === fileId ? { ...t, content, status: content === t.savedContent ? 'saved' : 'unsaved' } : t)),
    }))
    const existingTimer = saveTimers.get(fileId)
    if (existingTimer) clearTimeout(existingTimer)
    saveTimers.set(
      fileId,
      setTimeout(() => {
        get().saveNow(workspaceId, fileId)
      }, AUTOSAVE_DEBOUNCE_MS),
    )
  },

  saveNow: async (workspaceId, fileId) => {
    const tab = get().openTabs.find((t) => t.fileId === fileId)
    if (!tab || tab.content === tab.savedContent) return
    const timer = saveTimers.get(fileId)
    if (timer) clearTimeout(timer)

    set((state) => ({ openTabs: state.openTabs.map((t) => (t.fileId === fileId ? { ...t, status: 'saving' } : t)) }))
    try {
      await api.patch(`/workspaces/${workspaceId}/files/${fileId}`, { content: tab.content }, { headers: authHeaders() })
      set((state) => ({
        openTabs: state.openTabs.map((t) => (t.fileId === fileId ? { ...t, savedContent: t.content, status: 'saved' } : t)),
      }))
    } catch {
      set((state) => ({ openTabs: state.openTabs.map((t) => (t.fileId === fileId ? { ...t, status: 'error' } : t)) }))
    }
  },

  createFile: async (workspaceId, { name, parentId = null, isFolder = false, content = '' }) => {
    const { data } = await api.post(
      `/workspaces/${workspaceId}/files`,
      { name, parent_id: parentId, is_folder: isFolder, content },
      { headers: authHeaders() },
    )
    await get().loadFiles(workspaceId)
    return data
  },

  renameFile: async (workspaceId, fileId, name) => {
    await api.patch(`/workspaces/${workspaceId}/files/${fileId}`, { name }, { headers: authHeaders() })
    await get().loadFiles(workspaceId)
    set((state) => ({ openTabs: state.openTabs.map((t) => (t.fileId === fileId ? { ...t, name } : t)) }))
  },

  deleteFile: async (workspaceId, fileId) => {
    await api.delete(`/workspaces/${workspaceId}/files/${fileId}`, { headers: authHeaders() })
    get().closeTab(fileId)
    await get().loadFiles(workspaceId)
  },

  searchContent: async (workspaceId, query) => {
    if (!query.trim()) return []
    const { data } = await api.get(`/workspaces/${workspaceId}/files/search`, { params: { q: query }, headers: authHeaders() })
    return data
  },
}))
