import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 5000 })
// Longer timeout for WSL commands that may take up to 2 minutes
const apiWsl = axios.create({ baseURL: '/api', timeout: 130000 })

export const getHealth = () => api.get('/health').then(r => r.data)
export const getEntities = () => api.get('/entities').then(r => r.data)
export const getOverview = () => api.get('/overview').then(r => r.data)
export const getLogs = () => api.get('/logs').then(r => r.data)
export const getResults = () => api.get('/results').then(r => r.data)
export const getPackets = () => api.get('/packets').then(r => r.data)
export const getTracker = () => api.get('/tracker').then(r => r.data)
export const getConnectors = () => api.get('/connectors').then(r => r.data)
export const getComposioConnections = () => api.get('/composio/connections').then(r => r.data)
export const getQueueSummary = () => api.get('/queue/summary').then(r => r.data)
export const getQueueStatus = () => api.get('/queue/status').then(r => r.data)
export const getQueueItems = () => api.get('/queue/items').then(r => r.data)
export const getQueueItem = (id) => api.get(`/queue/items/${id}`).then(r => r.data)
export const getQueueNext = () => api.get('/queue/next').then(r => r.data)
export const getQueueReceipt = (path) => api.get('/queue/receipt', { params: { path } }).then(r => r.data)
export const getQueueArtifact = (path) => api.get('/queue/artifact', { params: { path } }).then(r => r.data)
export const createQueueItem = (data) => api.post('/queue/items', data).then(r => r.data)
export const getQueuePrompt = (id, target) => api.get(`/queue/items/${id}/prompt`, { params: { target } }).then(r => r.data)
export const attachQueueReceipt = (id, data) => api.post(`/queue/items/${id}/receipt`, data).then(r => r.data)
export const closeQueueItemReview = (id, data) => api.post(`/queue/items/${id}/review-close`, data).then(r => r.data)
export const updateQueueItemStatus = (id, status) => api.post(`/queue/items/${id}/status`, { status }).then(r => r.data)
export const updateTracker = (data) => api.post('/tracker', data).then(r => r.data)
export const createPacket = (data) => api.post('/packets', data).then(r => r.data)
export const launchEntity = (id) => api.post(`/launchers/${id}/launch`).then(r => r.data)

// WSL / AgenticOSClean runtime
export const wslStatus = () => apiWsl.get('/wsl/status').then(r => r.data)
export const wslHermes = (task) => apiWsl.post('/wsl/hermes', { task }).then(r => r.data)
export const wslClaude = (task) => apiWsl.post('/wsl/claude', { task }).then(r => r.data)
export const wslCodex = (task) => apiWsl.post('/wsl/codex', { task }).then(r => r.data)

export const telegramStatus = () => api.get('/connectors/telegram/status').then(r => r.data)
