import { useState, useEffect, useMemo } from 'react'
import { BufferGeometry, BufferAttribute, Scene } from 'three'
// @ts-expect-error three.js examples lack type declarations in this project's TS config
import { GLTFLoader, GLTF } from 'three/examples/jsm/loaders/GLTFLoader'
// @ts-expect-error three.js examples lack type declarations in this project's TS config
import * as BufferGeometryUtils from 'three/examples/jsm/utils/BufferGeometryUtils'
import { bearerHeaderForSameOrigin } from '../../lib/januaSso'

interface WorkerGeometryData {
  positions: Float32Array
  normals?: Float32Array
}

interface WorkerMessage {
  id: string
  success: boolean
  geometryData: WorkerGeometryData
  error?: string
}

interface WorkerLoaderResult {
  geometry: BufferGeometry | null
  scene: Scene | null
}

// We create a singleton worker so we don't spin up dozens of threads.
// Notice the ?worker syntax which Vite requires to bundle it correctly.
let stlWorkerInstance: Worker | null = null

// Simple global cache so we don't re-parse geometries that haven't changed URLs
const geometryCache = new Map<string, BufferGeometry | Promise<BufferGeometry>>()

// Tasks belong to the shared loader, not to the component that first asked.
// Unmounting one consumer must not remove the completion listener for the others.
const pendingTasks = new Map<Worker, Set<(message: string) => void>>()

function discardWorker(worker: Worker, message: string): void {
    if (stlWorkerInstance === worker) stlWorkerInstance = null
    for (const reject of [...(pendingTasks.get(worker) ?? [])]) reject(message)
    try { worker.terminate() } catch { /* already gone */ }
}

function loadSTL(url: string): Promise<BufferGeometry> {
    const cached = geometryCache.get(url)
    if (cached) return Promise.resolve(cached)

    const promise = new Promise<BufferGeometry>((resolve, reject) => {
        if (!stlWorkerInstance) {
            stlWorkerInstance = new Worker(new URL('../../workers/stlWorker.js', import.meta.url), { type: 'module' })
        }
        const worker = stlWorkerInstance
        const taskId = `task_${Math.random().toString(36).substring(7)}`
        let settled = false
        const tasks = pendingTasks.get(worker) ?? new Set<(message: string) => void>()
        pendingTasks.set(worker, tasks)
        const detach = () => {
            worker.removeEventListener('message', handleMessage)
            worker.removeEventListener('error', handleError)
            worker.removeEventListener('messageerror', handleMessageError)
            clearTimeout(timer)
            tasks.delete(fail)
            if (tasks.size === 0) pendingTasks.delete(worker)
        }
        const fail = (message: string) => {
            if (settled) return
            settled = true
            detach()
            reject(new Error(message))
        }
        const handleError = (event: ErrorEvent) => discardWorker(worker, `STL worker failed: ${event.message || 'unknown error'}`)
        const handleMessageError = () => discardWorker(worker, 'STL worker sent a message that could not be deserialized')
        const timer = setTimeout(() => discardWorker(worker, 'STL parse timed out after 120s'), 120_000)
        const handleMessage = (event: MessageEvent<WorkerMessage>) => {
            const { id, success, geometryData, error } = event.data
            if (id !== taskId || settled) return
            if (!success) return fail(`Failed to parse STL: ${error}`)
            const geometry = new BufferGeometry()
            try {
                geometry.setAttribute('position', new BufferAttribute(geometryData.positions, 3))
                if (geometryData.normals) geometry.setAttribute('normal', new BufferAttribute(geometryData.normals, 3))
                else geometry.computeVertexNormals()
                geometry.computeBoundingSphere()
                geometry.computeBoundingBox()
                settled = true
                detach()
                resolve(geometry)
            } catch (error) {
                geometry.dispose()
                fail(`Failed to reconstruct STL: ${String(error)}`)
            }
        }
        tasks.add(fail)
        worker.addEventListener('message', handleMessage)
        worker.addEventListener('error', handleError)
        worker.addEventListener('messageerror', handleMessageError)
        try {
            worker.postMessage({ url, id: taskId, authHeader: bearerHeaderForSameOrigin(url) })
        } catch (error) {
            discardWorker(worker, `STL worker could not start task: ${String(error)}`)
        }
    }).then(geometry => {
        geometryCache.set(url, geometry)
        return geometry
    }, error => {
        geometryCache.delete(url)
        throw error
    })
    geometryCache.set(url, promise)
    return promise
}

/** Load only the current URL while allowing other consumers to share STL work. */
export function useWorkerLoader(url: string | null | undefined, isGLTF: boolean = false): WorkerLoaderResult {
    const [gltfResult, setGltfResult] = useState<{ url: string; data: GLTF } | null>(null)
    const [stlResult, setStlResult] = useState<{ url: string; geometry: BufferGeometry } | null>(null)
    const currentGltf = isGLTF && gltfResult && gltfResult.url === url ? gltfResult.data : null

    useEffect(() => {
        if (!url) return
        let active = true
        if (isGLTF) {
            const loader = new GLTFLoader()
            const auth = bearerHeaderForSameOrigin(url)
            if (auth) loader.setRequestHeader({ Authorization: auth })
            loader.loadAsync(url).then((data: GLTF) => {
                if (active) setGltfResult({ url, data })
            }).catch((error: unknown) => { if (active) console.error('[WorkerLoader]', error) })
        } else {
            loadSTL(url).then(geometry => {
                if (active) setStlResult({ url, geometry })
            }).catch((error: unknown) => { if (active) console.error('[WorkerLoader]', error) })
        }
        return () => { active = false }
    }, [url, isGLTF])

    // GLTF parsing logic identical to the standard Viewer
    const gltfMergedGeom = useMemo((): BufferGeometry | null => {
        if (!isGLTF || !currentGltf) return null
        const geometries: BufferGeometry[] = []
        currentGltf.scene.updateMatrixWorld(true)
        currentGltf.scene.traverse((child: import('three').Object3D) => {
            const mesh = child as { isMesh?: boolean; geometry?: BufferGeometry; matrixWorld: import('three').Matrix4 }
            if (mesh.isMesh && mesh.geometry) {
                const clonedGeom = mesh.geometry.clone()
                clonedGeom.applyMatrix4(child.matrixWorld)
                geometries.push(clonedGeom)
            }
        })
        if (geometries.length === 0) return null
        if (geometries.length === 1) return geometries[0]
        return BufferGeometryUtils.mergeGeometries(geometries, false)
    }, [currentGltf, isGLTF])

    return {
        geometry: isGLTF ? gltfMergedGeom : (url && stlResult?.url === url ? stlResult.geometry : null),
        scene: currentGltf?.scene ?? null,
    }
}
