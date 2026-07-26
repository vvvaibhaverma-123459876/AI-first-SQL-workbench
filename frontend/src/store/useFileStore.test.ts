import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../services/api'
import { useFileStore } from './useFileStore'

vi.mock('../services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const WORKSPACE_ID = 'ws-1'
const FILE_ID = 'file-1'

beforeEach(() => {
  vi.clearAllMocks()
  useFileStore.setState({ files: [], openTabs: [], activeTabId: null, loadingFiles: false })
  vi.mocked(api.get).mockResolvedValue({ data: { id: FILE_ID, name: 'query.sql', content: 'SELECT 1;' } })
  vi.mocked(api.patch).mockResolvedValue({ data: {} })
})

describe('closeTab', () => {
  it('flushes a pending edit before removing the tab, instead of silently dropping it', async () => {
    // Reproduces the exact bug: edit a file, then close its tab before the
    // debounce timer would have fired on its own. Without flushing inside
    // closeTab, the edit since the last save is gone with zero trace and
    // api.patch is never called with the new content.
    await useFileStore.getState().openFile(WORKSPACE_ID, FILE_ID)
    useFileStore.getState().updateContent(WORKSPACE_ID, FILE_ID, 'SELECT 2; -- unsaved edit')

    await useFileStore.getState().closeTab(WORKSPACE_ID, FILE_ID)

    expect(api.patch).toHaveBeenCalledWith(
      `/workspaces/${WORKSPACE_ID}/files/${FILE_ID}`,
      { content: 'SELECT 2; -- unsaved edit' },
      expect.anything(),
    )
    expect(useFileStore.getState().openTabs.find((t) => t.fileId === FILE_ID)).toBeUndefined()
  })

  it('does not call the API again if there is nothing unsaved', async () => {
    await useFileStore.getState().openFile(WORKSPACE_ID, FILE_ID)
    await useFileStore.getState().closeTab(WORKSPACE_ID, FILE_ID)
    expect(api.patch).not.toHaveBeenCalled()
  })

  it('skips the flush when told to (deleteFile: the file no longer exists server-side)', async () => {
    await useFileStore.getState().openFile(WORKSPACE_ID, FILE_ID)
    useFileStore.getState().updateContent(WORKSPACE_ID, FILE_ID, 'edit that would 404 if flushed post-delete')

    await useFileStore.getState().closeTab(WORKSPACE_ID, FILE_ID, { flush: false })

    expect(api.patch).not.toHaveBeenCalled()
  })
})
