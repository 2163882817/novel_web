<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  checkChapter,
  deleteChapter,
  exportChapterTxt,
  finalizeChapter,
  generateVariants,
  genOutline,
  genTitles,
  getNovel,
  reviseChapter,
  saveChapter,
  streamWrite,
  updateChapter,
} from '../api'
import { fmtTime } from '../utils'

const route = useRoute()
const router = useRouter()
const novelId = Number(route.params.id)

const detail = ref(null) // { novel, volumes }
const loadError = ref('')

const volumes = computed(() => detail.value?.volumes || [])
const chapters = computed(() => volumes.value.flatMap((v) => v.chapters))
const nextChapterNo = computed(() => chapters.value.reduce((m, c) => Math.max(m, c.chapter_no), 0) + 1)

/* 面板状态：new = 写新章节，edit = 编辑已有章节 */
const mode = ref('new')
const currentId = ref(null)
const currentStatus = ref('')
const current = reactive({ title: '', content: '' })
const writeForm = reactive({ outline: '', previous_text: '' })

/* ① 细纲师 */
const plannerRaw = ref(null)
const planning = ref(false)
const planError = ref('')

/* ② 写手（流式） */
const output = ref('')
const variants = ref([])
const variantsWriting = ref(false)
const variantsError = ref('')
const writing = ref(false)
const writeError = ref('')
const stats = ref(null)
const saveTitle = ref('')
let abortCtrl = null

/* ③ 校对 / 修稿 / ④ 总结 */
const checkReport = ref(null)
const checking = ref(false)
const revising = ref(false)
const revisePreview = ref('')
const finalizeResult = ref(null)
const finalizing = ref(false)

const selectedIssues = computed(() => (checkReport.value?.issues || []).filter((it) => it.selected))

/* 标题师 */
const titleCandidates = ref([])
const titling = ref(false)
const currentChapterNo = ref(0)

const msg = ref('')
const msgOk = ref(true)
const charCount = computed(() => output.value.replace(/\s/g, '').length)

async function load() {
  loadError.value = ''
  try {
    detail.value = await getNovel(novelId)
    openNew()
  } catch (e) {
    loadError.value = e.message
  }
}
onMounted(load)

function resetTransient() {
  plannerRaw.value = null
  planError.value = ''
  output.value = ''
  variants.value = []
  variantsError.value = ''
  stats.value = null
  writeError.value = ''
  checkReport.value = null
  revisePreview.value = ''
  finalizeResult.value = null
  titleCandidates.value = []
  msg.value = ''
}

function openNew() {
  mode.value = 'new'
  currentId.value = null
  currentStatus.value = ''
  currentChapterNo.value = 0
  current.title = ''
  current.content = ''
  resetTransient()
  saveTitle.value = `第${nextChapterNo.value}章`
}

function openChapter(ch) {
  mode.value = 'edit'
  currentId.value = ch.id
  currentStatus.value = ch.status
  currentChapterNo.value = ch.chapter_no
  current.title = ch.title
  current.content = ch.content
  resetTransient()
  writeForm.outline = ch.detailed_outline || ''
  writeForm.previous_text = ''
}

/* ---------- ① 细纲师 ---------- */
function outlineToText(data) {
  const lines = []
  if (data.chapter_title) lines.push(`标题：${data.chapter_title}`)
  for (const s of data.scenes || []) {
    lines.push(
      `\n场景 ${s.scene_no}｜地点：${s.location || '未定'}｜出场：${(s.participants || []).join('、') || '未定'}`,
    )
    if (s.goal) lines.push(`  剧情作用：${s.goal}`)
    if (s.events) lines.push(`  事件：${s.events}`)
  }
  if (data.foreshadowings_planted?.length)
    lines.push('\n埋设伏笔：' + data.foreshadowings_planted.map((f) => `${f.title}（${f.description}）`).join('；'))
  if (data.foreshadowings_resolved?.length) lines.push(`回收伏笔：${data.foreshadowings_resolved.join('、')}`)
  if (data.hook) lines.push(`\n章末钩子：${data.hook}`)
  if (data.word_target) lines.push(`目标字数：${data.word_target} 字`)
  return lines.join('\n')
}

/* ---------- 标题师 ---------- */
async function onGenTitles() {
  titling.value = true
  titleCandidates.value = []
  try {
    const r = await genTitles({
      novel_id: novelId,
      content: mode.value === 'edit' ? current.content : output.value,
      outline: writeForm.outline,
      chapter_no: mode.value === 'edit' ? currentChapterNo.value : nextChapterNo.value,
    })
    titleCandidates.value = r.titles || []
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  } finally {
    titling.value = false
  }
}

function pickTitle(t) {
  if (mode.value === 'edit') current.title = t
  else saveTitle.value = t
  titleCandidates.value = []
}

async function onPlan() {
  planning.value = true
  planError.value = ''
  try {
    const data = await genOutline(novelId, nextChapterNo.value)
    plannerRaw.value = data
    writeForm.outline = outlineToText(data)
    if (data.chapter_title) saveTitle.value = data.chapter_title
  } catch (e) {
    planError.value = e.message
  } finally {
    planning.value = false
  }
}

async function onWriteVariants() {
  if (variantsWriting.value || !writeForm.outline.trim()) return
  variantsWriting.value = true
  variantsError.value = ''
  variants.value = []
  msg.value = ''
  try {
    const r = await generateVariants({
      novel_id: novelId,
      outline: writeForm.outline,
      previous_text: writeForm.previous_text,
      max_tokens: 4096,
    })
    variants.value = r.variants || []
    stats.value = r
  } catch (e) {
    variantsError.value = e.message
  } finally {
    variantsWriting.value = false
  }
}

function importVariant(variant) {
  output.value = variant.content
  msg.value = `已将版本 ${variant.label} 导入主编辑器，其他版本仍保留为素材`
  msgOk.value = true
}

async function copyVariant(variant) {
  try {
    await navigator.clipboard.writeText(variant.content)
    msg.value = `版本 ${variant.label} 已复制，可粘贴到主编辑器合并`
    msgOk.value = true
  } catch {
    msg.value = '复制失败，请手动选择正文后复制'
    msgOk.value = false
  }
}

/* ---------- ② 写手 ---------- */
async function onWrite() {
  if (writing.value) return
  output.value = ''
  writeError.value = ''
  stats.value = null
  msg.value = ''
  writing.value = true
  abortCtrl = new AbortController()
  try {
    const done = await streamWrite(
      {
        novel_id: novelId,
        outline: writeForm.outline,
        previous_text: writeForm.previous_text,
        max_tokens: 4096,
      },
      {
        onDelta: (t) => (output.value += t),
        onError: (m) => (writeError.value = m),
        signal: abortCtrl.signal,
      },
    )
    stats.value = done
  } catch (e) {
    if (e.name !== 'AbortError') writeError.value = e.message
  } finally {
    writing.value = false
  }
}

function onStop() {
  abortCtrl && abortCtrl.abort()
}

async function onSaveAsChapter() {
  if (!output.value.trim()) {
    msg.value = '还没有生成内容'
    msgOk.value = false
    return
  }
  try {
    const ch = await saveChapter({
      novel_id: novelId,
      title: saveTitle.value || `第${nextChapterNo.value}章`,
      content: output.value,
      detailed_outline: writeForm.outline,
    })
    writeForm.previous_text = '' // 下一章自动取本章结尾衔接
    msg.value = `已保存：${ch.title}（${ch.word_count} 字）`
    msgOk.value = true
    await load()
    openChapter(ch)
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  }
}

async function onSaveEdit() {
  if (!currentId.value) return
  try {
    await updateChapter(currentId.value, {
      title: current.title,
      content: current.content,
      detailed_outline: writeForm.outline,
    })
    msg.value = '已保存修改'
    msgOk.value = true
    await load()
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  }
}

/* ---------- ③ 校对 ---------- */
async function onCheck() {
  if (!currentId.value) return
  checking.value = true
  checkReport.value = null
  try {
    const r = await checkChapter(currentId.value)
    // 默认全选，方便一键修复
    checkReport.value = { ...r, issues: (r.issues || []).map((it) => ({ ...it, selected: true })) }
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  } finally {
    checking.value = false
  }
}

/* ---------- 修稿：按校对意见一键修复 ---------- */
async function onRevise() {
  if (!currentId.value || !selectedIssues.value.length) return
  revising.value = true
  revisePreview.value = ''
  try {
    const r = await reviseChapter(currentId.value, { issues: selectedIssues.value })
    revisePreview.value = r.content
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  } finally {
    revising.value = false
  }
}

function onApplyRevision() {
  current.content = revisePreview.value
  revisePreview.value = ''
  checkReport.value = null // 修订后报告已过期，建议重新校对
  msg.value = '已应用修订，请检查后点「保存修改」'
  msgOk.value = true
}

/* ---------- ④ 定稿（更新记忆） ---------- */
async function onFinalize() {
  if (!currentId.value) return
  finalizing.value = true
  finalizeResult.value = null
  try {
    finalizeResult.value = await finalizeChapter(currentId.value)
    currentStatus.value = '已定稿'
    msg.value = '记忆已更新'
    msgOk.value = true
    await load()
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  } finally {
    finalizing.value = false
  }
}

async function onDeleteCurrent() {
  if (!currentId.value) return
  if (!confirm(`确定删除「${current.title}」？`)) return
  try {
    await deleteChapter(currentId.value)
    await load()
    openNew()
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  }
}

/* ---------- 导出 txt ---------- */
const exportShow = ref(false)
const exportSel = ref(new Set())
const exportIncludeOutline = ref(false)
const exporting = ref(false)

function openExport() {
  exportSel.value = new Set(chapters.value.map((c) => c.id)) // 默认全选
  exportIncludeOutline.value = false
  exportShow.value = true
}

function toggleExport(id) {
  if (exportSel.value.has(id)) exportSel.value.delete(id)
  else exportSel.value.add(id)
}

function exportSelectAll() {
  exportSel.value = new Set(chapters.value.map((c) => c.id))
}

function exportClear() {
  exportSel.value = new Set()
}

async function onExport() {
  if (!exportSel.value.size) return
  exporting.value = true
  try {
    const { blob, filename } = await exportChapterTxt(novelId, {
      chapter_ids: [...exportSel.value],
      include_outline: exportIncludeOutline.value,
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
    exportShow.value = false
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <div>
    <div v-if="loadError" class="msg err">{{ loadError }}</div>

    <template v-else-if="detail">
      <div class="novel-head">
        <button class="link" @click="router.push('/')">← 返回书架</button>
        <h2>{{ detail.novel.title }}</h2>
        <span v-if="detail.novel.genre" class="tag">{{ detail.novel.genre }}</span>
        <span v-if="detail.novel.style" class="tag">{{ detail.novel.style }}</span>
        <span class="hint">{{ chapters.length }} 章 · 更新于 {{ fmtTime(detail.novel.updated_at) }}</span>
        <div class="spacer"></div>
        <button @click="openExport">⬇ 导出 txt</button>
        <button class="link" @click="router.push(`/novel/${novelId}/settings`)">🧠 设定 / 记忆</button>
        <button class="primary" @click="openNew">＋ 写新章节</button>
      </div>

      <div class="workbench">
        <!-- 左：章节列表 -->
        <aside class="chapter-list card">
          <div v-for="v in volumes" :key="v.id">
            <h3 class="volume-title">{{ v.title }}</h3>
            <div
              v-for="ch in v.chapters"
              :key="ch.id"
              class="chapter-item"
              :class="{ active: mode === 'edit' && currentId === ch.id }"
              @click="openChapter(ch)"
            >
              <span class="ch-label">
                <span class="dot" :class="ch.status === '已定稿' ? 'b-green' : 'b-gray'" :title="ch.status"></span>
                第{{ ch.chapter_no }}章 {{ ch.title }}
              </span>
              <span class="hint">{{ ch.word_count }} 字</span>
            </div>
          </div>
          <p v-if="!chapters.length" class="hint">
            还没有章节。建议流程：✨ 生成细纲 → 开始写作 → 保存 → 校对 → 定稿（更新记忆）
          </p>
        </aside>

        <!-- 右：写作 / 编辑面板 -->
        <section class="card panel">
          <!-- ============ 写新章节 ============ -->
          <template v-if="mode === 'new'">
            <h2>写新章节 <span class="hint">第 {{ nextChapterNo }} 章（章号自动）</span></h2>

            <div class="row">
              <button class="primary" :disabled="planning || writing" @click="onPlan">
                {{ planning ? '生成细纲中…' : '✨ AI 生成细纲（细纲师）' }}
              </button>
            </div>
            <p v-if="planError" class="msg err">{{ planError }}</p>

            <div v-if="plannerRaw" class="plan-preview">
              <h3>{{ plannerRaw.chapter_title || `第${nextChapterNo}章` }}</h3>
              <div v-for="s in plannerRaw.scenes" :key="s.scene_no" class="plan-scene">
                <b>场景 {{ s.scene_no }}</b>
                ｜{{ s.location || '地点未定' }}｜{{ (s.participants || []).join('、') || '出场未定' }}
                <div v-if="s.goal" class="hint">剧情作用：{{ s.goal }}</div>
                <div v-if="s.events">{{ s.events }}</div>
              </div>
              <div class="plan-foot">
                <span v-if="plannerRaw.foreshadowings_planted?.length" class="tag tag-new">
                  埋设：{{ plannerRaw.foreshadowings_planted.map((f) => f.title).join('、') }}
                </span>
                <span v-if="plannerRaw.foreshadowings_resolved?.length" class="tag tag-done">
                  回收：{{ plannerRaw.foreshadowings_resolved.join('、') }}
                </span>
              </div>
              <div v-if="plannerRaw.hook" class="plan-hook">🪝 {{ plannerRaw.hook }}</div>
            </div>

            <label>细纲（可编辑，已同步为上文生成结果）</label>
            <textarea v-model="writeForm.outline" rows="5" placeholder="留空则 AI 自行安排；建议先点「✨ AI 生成细纲」"></textarea>
            <label>前文衔接 <span class="hint">留空自动取上一章结尾 800 字</span></label>
            <textarea v-model="writeForm.previous_text" rows="2" placeholder="也可手动粘贴特定片段"></textarea>
            <div class="row">
              <button class="primary" :disabled="writing || planning || variantsWriting" @click="onWrite">
                {{ writing ? '写作中…' : '开始写作（单版）' }}
              </button>
              <button :disabled="writing || planning || variantsWriting || !writeForm.outline.trim()" @click="onWriteVariants">
                {{ variantsWriting ? '生成 A/B/C 中…' : '生成 A/B/C 三版' }}
              </button>
              <button :disabled="!writing" @click="onStop">停止</button>
            </div>
            <p v-if="writeError" class="msg err">{{ writeError }}</p>
            <p v-if="variantsError" class="msg err">{{ variantsError }}</p>

            <div v-if="variants.length" class="variants-panel">
              <div class="output-head">
                <span>三版正文素材</span>
                <span class="hint">选择一版导入主编辑器，其他版本不会删除</span>
              </div>
              <div class="variant-grid">
                <article v-for="variant in variants" :key="variant.label" class="variant-card">
                  <div class="variant-head">
                    <strong>版本 {{ variant.label }}</strong>
                    <span class="hint">{{ variant.word_count }} 字</span>
                  </div>
                  <pre class="variant-body" tabindex="0">{{ variant.content }}</pre>
                  <div class="row variant-actions">
                    <button class="primary" @click="importVariant(variant)">导入主编辑器</button>
                    <button @click="copyVariant(variant)">复制全文</button>
                  </div>
                </article>
              </div>
            </div>

            <div v-show="output || writing" class="output">
              <div class="output-head">
                <span>{{ writing ? '正在生成…' : `主编辑器 · ${charCount} 字` }}</span>
                <span v-if="variants.length" class="hint">可粘贴素材面板片段进行合并</span>
              </div>
              <textarea v-model="output" rows="14" class="editor" :placeholder="writing ? '正文生成中…' : '选择版本导入，或直接编辑主稿'"></textarea>
              <div class="row save-row">
                <input v-model="saveTitle" class="grow" placeholder="章节标题" />
                <button :disabled="titling" :title="'AI 起标题'" @click="onGenTitles">✨</button>
                <button class="primary" :disabled="!output || writing || variantsWriting" @click="onSaveAsChapter">保存为章节</button>
              </div>
              <div v-if="titleCandidates.length" class="title-cands">
                <span class="hint">候选标题（点击选用）：</span>
                <button v-for="(t, i) in titleCandidates" :key="i" class="cand" @click="pickTitle(t)">{{ t }}</button>
              </div>
              <p v-if="msg" class="msg" :class="msgOk ? 'ok' : 'err'">{{ msg }}</p>
              <p v-if="stats && !msg" class="msg ok">生成完成：耗时 {{ (stats.duration_ms / 1000).toFixed(1) }} s</p>
            </div>
          </template>

          <!-- ============ 编辑已有章节 ============ -->
          <template v-else>
            <h2>
              编辑章节
              <span class="badge" :class="currentStatus === '已定稿' ? 'b-green' : 'b-gray'">
                {{ currentStatus || '草稿' }}
              </span>
            </h2>
            <label>标题</label>
            <div class="row" style="margin-top: 4px">
              <input v-model="current.title" class="grow" />
              <button :disabled="titling" @click="onGenTitles">
                {{ titling ? '起名中…' : '✨ AI 起标题' }}
              </button>
            </div>
            <div v-if="titleCandidates.length" class="title-cands">
              <span class="hint">候选标题（点击选用）：</span>
              <button v-for="(t, i) in titleCandidates" :key="i" class="cand" @click="pickTitle(t)">{{ t }}</button>
            </div>
            <label>正文（可直接修改）</label>
            <textarea v-model="current.content" rows="14" class="editor"></textarea>
            <label>细纲</label>
            <textarea v-model="writeForm.outline" rows="3" placeholder="本章细纲，供校对与 AI 重写参考"></textarea>
            <div class="row">
              <button class="primary" @click="onSaveEdit">保存修改</button>
              <button @click="openNew">写新章节</button>
              <button class="danger" @click="onDeleteCurrent">删除本章</button>
              <div class="spacer"></div>
              <button :disabled="checking" @click="onCheck">{{ checking ? '校对中…' : '🔍 校对' }}</button>
              <button class="primary" :disabled="finalizing" @click="onFinalize">
                {{ finalizing ? '更新记忆中…' : '📝 定稿（更新记忆）' }}
              </button>
            </div>
            <p v-if="msg" class="msg" :class="msgOk ? 'ok' : 'err'">{{ msg }}</p>

            <!-- 校对报告 -->
            <div v-if="checkReport" class="check-report">
              <div class="output-head">
                <span>校对报告</span>
                <span class="badge" :class="checkReport.verdict === 'pass' ? 'b-green' : 'b-high'">
                  {{ checkReport.verdict === 'pass' ? '✓ 通过' : '需修改' }}
                </span>
              </div>
              <div v-for="(it, i) in checkReport.issues" :key="i" class="issue" :class="it.severity">
                <label class="issue-check">
                  <input type="checkbox" v-model="it.selected" />
                  <span class="badge" :class="`b-${it.severity}`">{{ it.severity }}</span>
                  <b>{{ it.type }}</b>
                  <span class="hint">{{ it.location }}</span>
                </label>
                <div>{{ it.description }}</div>
                <div v-if="it.suggestion" class="hint">建议：{{ it.suggestion }}</div>
              </div>
              <p v-if="!checkReport.issues.length" class="msg ok">未发现问题</p>
              <div v-else class="row">
                <button class="primary" :disabled="revising || !selectedIssues.length" @click="onRevise">
                  {{ revising ? 'AI 修稿中…' : `🛠 AI 修复所选问题（${selectedIssues.length}）` }}
                </button>
              </div>
            </div>

            <!-- 修订稿预览 -->
            <div v-if="revisePreview" class="revise-preview">
              <div class="output-head">
                <span>修订稿预览（只改问题相关处，其余原样保留）</span>
              </div>
              <pre class="output-body">{{ revisePreview }}</pre>
              <div class="row">
                <button class="primary" @click="onApplyRevision">应用修订</button>
                <button @click="revisePreview = ''">放弃</button>
              </div>
            </div>

            <!-- 定稿结果 -->
            <div v-if="finalizeResult" class="finalize-result">
              <p class="msg ok">
                记忆已更新：角色状态 {{ finalizeResult.characters_updated }} 处 ·
                新埋伏笔 {{ finalizeResult.foreshadowings_planted }} 条 ·
                回收伏笔 {{ finalizeResult.foreshadowings_resolved }} 条
              </p>
              <div class="hint">章摘要：{{ finalizeResult.summary }}</div>
            </div>
          </template>
        </section>
      </div>

      <!-- 导出弹窗 -->
      <div v-if="exportShow" class="overlay" @click.self="exportShow = false">
        <div class="modal modal-lg">
          <h3>导出为 txt</h3>
          <p class="hint">勾选要导出的章节；文件含书名、卷名与章标题，适配阅读器与 AI 改编工具</p>
          <div class="row" style="margin-top: 8px">
            <button @click="exportSelectAll">全选</button>
            <button @click="exportClear">清空</button>
          </div>
          <div class="export-list">
            <template v-for="v in volumes" :key="v.id">
              <div class="volume-title">{{ v.title }}</div>
              <label v-for="ch in v.chapters" :key="ch.id" class="export-item">
                <input
                  type="checkbox"
                  :checked="exportSel.has(ch.id)"
                  @change="toggleExport(ch.id)"
                />
                <span>第{{ ch.chapter_no }}章 {{ ch.title }}</span>
                <span class="hint">{{ ch.word_count }} 字</span>
              </label>
            </template>
            <p v-if="!chapters.length" class="hint">还没有章节可导出</p>
          </div>
          <label class="export-opt">
            <input type="checkbox" v-model="exportIncludeOutline" />
            包含每章细纲（场景/人物/事件，方便 AI 漫剧分镜参考）
          </label>
          <div class="row">
            <button class="primary" :disabled="!exportSel.size || exporting" @click="onExport">
              {{ exporting ? '导出中…' : `下载 txt（已选 ${exportSel.size} 章）` }}
            </button>
            <button @click="exportShow = false">取消</button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
