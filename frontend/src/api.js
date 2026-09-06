const configuredBase = import.meta.env.VITE_API_BASE_URL || '/api'
const BASE = configuredBase.replace(/\/$/, '')

async function readDetail(r) {
  let msg = '请求失败'
  try {
    msg = (await r.json()).detail || msg
  } catch {
    /* 非 JSON 响应，保留默认文案 */
  }
  return msg
}

async function request(method, path, body) {
  const r = await fetch(`${BASE}${path}`, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) throw new Error(await readDetail(r))
  return r.json()
}

/* ---------- API 配置 ---------- */
export const getConfig = () => request('GET', '/config')
export const saveConfig = (p) => request('PUT', '/config', p)

export async function testConnection() {
  const r = await fetch(`${BASE}/config/test`, { method: 'POST' })
  const data = await r.json()
  if (!r.ok) throw new Error(data.detail || '测试失败')
  return data
}

/* ---------- 小说书架 ---------- */
export const listNovels = () => request('GET', '/novels')
export const createNovel = (p) => request('POST', '/novels', p)
export const getNovel = (id) => request('GET', `/novels/${id}`)
export const updateNovel = (id, p) => request('PUT', `/novels/${id}`, p)
export const deleteNovel = (id) => request('DELETE', `/novels/${id}`)

/* ---------- 章节 ---------- */
export const saveChapter = (p) => request('POST', '/chapters', p)
export const updateChapter = (id, p) => request('PUT', `/chapters/${id}`, p)
export const deleteChapter = (id) => request('DELETE', `/chapters/${id}`)

/* ---------- 导出 ---------- */
export async function exportChapterTxt(novelId, payload) {
  const r = await fetch(`${BASE}/novels/${novelId}/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await readDetail(r))
  const blob = await r.blob()
  const cd = r.headers.get('Content-Disposition') || ''
  let filename = 'export.txt'
  const m = cd.match(/filename\*=UTF-8''([^;]+)/)
  if (m) filename = decodeURIComponent(m[1])
  return { blob, filename }
}

/* ---------- 设定导入 ---------- */
export const importDoc = (novelId, p) => request('POST', `/novels/${novelId}/import`, p)
export const clearWritingRestrictions = (novelId) =>
  request('DELETE', `/novels/${novelId}/writing-restrictions`)

/* ---------- 记忆系统 ---------- */
export const genOutline = (novelId, chapterNo) =>
  request('POST', `/novels/${novelId}/next-outline?chapter_no=${chapterNo || 0}`)
export const genTitles = (p) => request('POST', '/titles', p)
export const checkChapter = (id) => request('POST', `/chapters/${id}/check`)
export const reviseChapter = (id, p) => request('POST', `/chapters/${id}/revise`, p)
export const finalizeChapter = (id) => request('POST', `/chapters/${id}/finalize`)
export const getMemory = (novelId) => request('GET', `/novels/${novelId}/memory`)
export const updateVolume = (id, p) => request('PUT', `/volumes/${id}`, p)
export const createVolume = (novelId, p) => request('POST', `/novels/${novelId}/volumes`, p)
export const genVolumeOutline = (novelId) => request('POST', `/novels/${novelId}/volume-outline`)
export const genVolumeSummary = (volumeId) => request('POST', `/volumes/${volumeId}/summary`)
export const createCharacter = (novelId, p) => request('POST', `/novels/${novelId}/characters`, p)
export const updateCharacter = (id, p) => request('PUT', `/characters/${id}`, p)
export const deleteCharacter = (id) => request('DELETE', `/characters/${id}`)
export const createForeshadowing = (novelId, p) => request('POST', `/novels/${novelId}/foreshadowings`, p)
export const updateForeshadowing = (id, p) => request('PUT', `/foreshadowings/${id}`, p)
export const deleteForeshadowing = (id) => request('DELETE', `/foreshadowings/${id}`)

/* ---------- 流式写作 ---------- */
/** SSE 流式写作：逐字回调 onDelta，事件流结束时返回 done 统计 */
export async function streamWrite(payload, { onDelta, onError, signal }) {
  const r = await fetch(`${BASE}/write/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
  if (!r.ok || !r.body) throw new Error(await readDetail(r))

  const reader = r.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  const done = {}

  while (true) {
    const { done: isDone, value } = await reader.read()
    if (isDone) break
    buf += decoder.decode(value, { stream: true })
    const parts = buf.split('\n\n')
    buf = parts.pop()
    for (const part of parts) {
      if (!part.startsWith('data: ')) continue
      let evt
      try {
        evt = JSON.parse(part.slice(6))
      } catch {
        continue
      }
      if (evt.type === 'delta') onDelta(evt.text)
      else if (evt.type === 'error') onError(evt.message)
      else if (evt.type === 'done') Object.assign(done, evt)
    }
  }
  return done
}
