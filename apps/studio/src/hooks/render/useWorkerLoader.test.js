import React from 'react'
import { act, cleanup, renderHook } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { Scene, Mesh, BoxGeometry, MeshStandardMaterial } from 'three'

const { loadAsync } = vi.hoisted(() => ({ loadAsync: vi.fn() }))
vi.mock('three/examples/jsm/loaders/GLTFLoader', () => ({
  GLTFLoader: class { loadAsync = loadAsync; setRequestHeader = vi.fn() },
}))
vi.mock('../../lib/januaSso', () => ({ bearerHeaderForSameOrigin: () => null }))

let useWorkerLoader, workers
class MockWorker extends EventTarget {
  sent = []
  constructor() { super(); workers.push(this) }
  postMessage(message) { this.sent.push(message) }
  terminate = vi.fn()
  complete(index, size = 1) {
    this.dispatchEvent(new MessageEvent('message', { data: {
      id: this.sent[index].id, success: true,
      geometryData: { positions: new Float32Array([0, 0, 0, size, 0, 0, 0, size, 0]) },
    } }))
  }
}
function scene() {
  const value = new Scene()
  value.add(new Mesh(new BoxGeometry(), new MeshStandardMaterial()))
  return { scene: value }
}

beforeEach(async () => {
  vi.resetModules()
  vi.useFakeTimers()
  workers = []
  vi.stubGlobal('Worker', MockWorker)
  loadAsync.mockReset()
  vi.spyOn(console, 'error').mockImplementation(() => {})
  ;({ useWorkerLoader } = await import('./useWorkerLoader'))
})
afterEach(() => {
  cleanup()
  vi.clearAllTimers()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useWorkerLoader lifecycle', () => {
  it('returns no geometry or scene for an absent GLB URL', () => {
    const { result } = renderHook(() => useWorkerLoader(undefined, true))
    expect(result.current).toEqual({ geometry: null, scene: null })
    expect(loadAsync).not.toHaveBeenCalled()
  })

  it('settles synchronous worker dispatch failures and permits a new worker', async () => {
    vi.spyOn(MockWorker.prototype, 'postMessage').mockImplementationOnce(() => { throw new Error('dispatch failed') })
    const first = renderHook(() => useWorkerLoader('dispatch.stl'))
    await act(async () => {})
    expect(workers[0].terminate).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
    first.unmount()
    const next = renderHook(() => useWorkerLoader('dispatch.stl'))
    await act(async () => workers[1].complete(0))
    expect(next.result.current.geometry).not.toBeNull()
  })

  it('keeps a shared STL request alive when the initiating consumer unmounts', async () => {
    const first = renderHook(() => useWorkerLoader('shared.stl'))
    const second = renderHook(() => useWorkerLoader('shared.stl'))
    first.unmount()
    expect(workers[0].sent).toHaveLength(1)
    await act(async () => workers[0].complete(0))
    expect(second.result.current.geometry?.getAttribute('position').count).toBe(3)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('settles the shared request across StrictMode effect cleanup/replay', async () => {
    const { result } = renderHook(() => useWorkerLoader('strict.stl'), {
      wrapper: ({ children }) => React.createElement(React.StrictMode, null, children),
    })
    await act(async () => workers[0].complete(0))
    expect(result.current.geometry).not.toBeNull()
    expect(workers[0].sent).toHaveLength(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('does not show previous STL geometry while a new URL loads or after clearing', async () => {
    const { result, rerender } = renderHook(({ url }) => useWorkerLoader(url), { initialProps: { url: 'old.stl' } })
    await act(async () => workers[0].complete(0))
    expect(result.current.geometry).not.toBeNull()
    rerender({ url: 'new.stl' })
    expect(result.current.geometry).toBeNull()
    await act(async () => workers[0].complete(1, 2))
    expect(result.current.geometry.boundingBox.max.x).toBe(2)
    rerender({ url: null })
    expect(result.current.geometry).toBeNull()
  })

  it('ignores a late shared STL result after the consumer changes URL', async () => {
    const owner = renderHook(() => useWorkerLoader('slow.stl'))
    const { result, rerender } = renderHook(({ url }) => useWorkerLoader(url), { initialProps: { url: 'slow.stl' } })
    rerender({ url: 'fast.stl' })
    await act(async () => workers[0].complete(1, 2))
    await act(async () => workers[0].complete(0, 1))
    expect(result.current.geometry.boundingBox.max.x).toBe(2)
    expect(owner.result.current.geometry.boundingBox.max.x).toBe(1)
  })

  it('ignores late GLB results and hides stale scenes when switching formats', async () => {
    let resolveOld, resolveNew
    loadAsync.mockReturnValueOnce(new Promise(r => { resolveOld = r })).mockReturnValueOnce(new Promise(r => { resolveNew = r }))
    const { result, rerender } = renderHook(({ url, glb }) => useWorkerLoader(url, glb), { initialProps: { url: 'old.glb', glb: true } })
    rerender({ url: 'new.glb', glb: true })
    const newer = scene()
    await act(async () => resolveNew(newer))
    await act(async () => resolveOld(scene()))
    expect(result.current.scene).toBe(newer.scene)
    rerender({ url: 'pending.stl', glb: false })
    expect(result.current).toEqual({ geometry: null, scene: null })
  })

  it('releases failed worker requests so remount can retry', async () => {
    const first = renderHook(() => useWorkerLoader('failed.stl'))
    await act(async () => workers[0].dispatchEvent(new ErrorEvent('error', { message: 'crash' })))
    first.unmount()
    const second = renderHook(() => useWorkerLoader('failed.stl'))
    expect(workers).toHaveLength(2)
    await act(async () => workers[1].complete(0))
    expect(second.result.current.geometry).not.toBeNull()
  })

  it('clears all pending tasks when a timed-out singleton is discarded', async () => {
    renderHook(() => useWorkerLoader('timeout-one.stl'))
    await act(async () => vi.advanceTimersByTimeAsync(1000))
    renderHook(() => useWorkerLoader('timeout-two.stl'))
    await act(async () => vi.advanceTimersByTimeAsync(119000))
    expect(workers[0].terminate).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
    renderHook(() => useWorkerLoader('timeout-two.stl'))
    expect(workers).toHaveLength(2)
  })
})
