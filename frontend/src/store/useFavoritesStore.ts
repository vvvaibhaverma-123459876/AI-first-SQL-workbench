import { create } from 'zustand'
import api from '../services/api'
import type { FavoriteResourceType, FavoriteSummary } from '../types'
import { useAuthStore } from './useAuthStore'

function authHeaders() {
  const token = useAuthStore.getState().token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

type FavoritesState = {
  favorites: FavoriteSummary[]

  loadFavorites: (workspaceId: string) => Promise<void>
  isFavorited: (resourceType: FavoriteResourceType, resourceId: string) => boolean
  toggleFavorite: (workspaceId: string, resourceType: FavoriteResourceType, resourceId: string) => Promise<void>
}

export const useFavoritesStore = create<FavoritesState>((set, get) => ({
  favorites: [],

  loadFavorites: async (workspaceId) => {
    const { data } = await api.get(`/workspaces/${workspaceId}/favorites`, { headers: authHeaders() })
    set({ favorites: data })
  },

  isFavorited: (resourceType, resourceId) => get().favorites.some((f) => f.resource_type === resourceType && f.resource_id === resourceId),

  toggleFavorite: async (workspaceId, resourceType, resourceId) => {
    const plural = resourceType === 'file' ? 'files' : 'dashboards'
    if (get().isFavorited(resourceType, resourceId)) {
      await api.delete(`/workspaces/${workspaceId}/${plural}/${resourceId}/favorite`, { headers: authHeaders() })
    } else {
      await api.put(`/workspaces/${workspaceId}/${plural}/${resourceId}/favorite`, {}, { headers: authHeaders() })
    }
    // Refetch rather than patch state locally: the server response for a
    // PUT doesn't include resource_name, and the list is small enough that
    // a round trip is simpler and never drifts from the server's view.
    await get().loadFavorites(workspaceId)
  },
}))
