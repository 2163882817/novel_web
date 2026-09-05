<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  clearWritingRestrictions,
  createCharacter,
  createForeshadowing,
  createVolume,
  deleteCharacter,
  deleteForeshadowing,
  genVolumeOutline,
  genVolumeSummary,
  getMemory,
  importDoc,
  updateCharacter,
  updateForeshadowing,
  updateVolume,
} from '../api'
import { fmtTime } from '../utils'

const route = useRoute()
const router = useRouter()
const novelId = Number(route.params.id)

const memory = ref(null)
const tab = ref('characters')
const msg = ref('')
const msgOk = ref(true)

const CHAR_KEYS = ['外貌', '性格', '目标', '关系', '位置', '情感']

/* ---------- 人物卡 ---------- */
const charForm = reactive({ id: null, name: '', role: '配角', card: {} })

function newCharacter() {
  charForm.id = null
  charForm.name = ''
  charForm.role = '配角'
  charForm.card = {}
}

function editCharacter(c) {
  charForm.id = c.id
  charForm.name = c.name
  charForm.role = c.role
  charForm.card = { ...(c.card || {}) }
}

async function onSaveCharacter() {
  if (!charForm.name.trim()) {
    msg.value = '请填写角色名'
    msgOk.value = false
    return
  }
  try {
    if (charForm.id)
      await updateCharacter(charForm.id, { name: charForm.name, role: charForm.role, card: charForm.card })
    else await createCharacter(novelId, { name: charForm.name, role: charForm.role, card: charForm.card })
    msg.value = '已保存'
    msgOk.value = true
    newCharacter()
    await load()
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  }
}

async function onDeleteCharacter(c) {
  if (!confirm(`删除人物卡「${c.name}」？`)) return
  try {
    await deleteCharacter(c.id)
    await load()
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  }
}

/* ---------- 伏笔库 ---------- */
const fForm = reactive({ id: null, title: '', description: '', status: '待回收' })
const FS_STATUS = ['待回收', '已回收', '废弃']

function newForeshadowing() {
  fForm.id = null
  fForm.title = ''
  fForm.description = ''
  fForm.status = '待回收'
}

function editForeshadowing(f) {
  fForm.id = f.id
  fForm.title = f.title
  fForm.description = f.description
  fForm.status = f.status
}

async function onSaveForeshadowing() {
  if (!fForm.title.trim()) {
    msg.value = '请填写伏笔标题'
    msgOk.value = false
    return
  }
  try {
    if (fForm.id)
      await updateForeshadowing(fForm.id, { title: fForm.title, description: fForm.description, status: fForm.status })
    else await createForeshadowing(novelId, { title: fForm.title, description: fForm.description, status: fForm.status })
    msg.value = '已保存'
    msgOk.value = true
    newForeshadowing()
    await load()
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  }
}

async function onDeleteForeshadowing(f) {
  if (!confirm(`删除伏笔「${f.title}」？`)) return
  try {
    await deleteForeshadowing(f.id)
    await load()
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  }
}

/* ---------- 卷管理 ---------- */
const volumeForm = reactive({ id: null, title: '', status: '连载中', outline: '', summary: '' })
const showNewVolume = ref(false)
const newVolForm = reactive({ title: '', outline: '' })
const genningOutline = ref(false)
const genningSummary = ref(false)
const creatingVol = ref(false)

function selectVolume(v) {
  volumeForm.id = v.id
  volumeForm.title = v.title
  volumeForm.status = v.status
  volumeForm.outline = v.outline
  volumeForm.summary = v.summary
}

function openNewVolume() {
  const nextNo = (memory.value?.volumes?.length || 0) + 1
  newVolForm.title = `第${nextNo}卷`
  newVolForm.outline = ''
  showNewVolume.value = true
}

async function onGenVolumeOutline() {
  genningOutline.value = true
  try {
    const r = await genVolumeOutline(novelId)
    if (r.volume_title) newVolForm.title = r.volume_title
    newVolForm.outline = r.outline
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  } finally {
    genningOutline.value = false
  }
}

async function onCreateVolume() {
  creatingVol.value = true
  try {
    const v = await createVolume(novelId, { title: newVolForm.title, outline: newVolForm.outline })
    showNewVolume.value = false
    msg.value = `已开新卷：${v.title}（上一卷已自动完结）`
    msgOk.value = true
    await load()
    const fresh = memory.value.volumes.find((x) => x.id === v.id)
    if (fresh) selectVolume(fresh)
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  } finally {
    creatingVol.value = false
  }
}

async function onSaveVolume() {
  if (!volumeForm.id) return
  try {
    await updateVolume(volumeForm.id, {
      title: volumeForm.title,
      outline: volumeForm.outline,
      status: volumeForm.status,
    })
    msg.value = '卷已保存'
    msgOk.value = true
    await load()
    const fresh = memory.value.volumes.find((x) => x.id === volumeForm.id)
    if (fresh) selectVolume(fresh)
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  }
}

async function onGenVolumeSummary() {
  if (!volumeForm.id) return
  genningSummary.value = true
  try {
    const r = await genVolumeSummary(volumeForm.id)
    volumeForm.summary = r.summary
    msg.value = '卷摘要已生成'
    msgOk.value = true
    await load()
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  } finally {
    genningSummary.value = false
  }
}

/* ---------- 设定导入 ---------- */
const importTexts = reactive({ bible: '', outline: '', characters: '', restrictions: '' })
const importMode = ref('replace')
const importing = ref(false)

function onFile(e, kind) {
  const f = e.target.files && e.target.files[0]
  if (!f) return
  const reader = new FileReader()
  reader.onload = () => {
    importTexts[kind] = String(reader.result || '')
  }
  reader.readAsText(f, 'utf-8')
  e.target.value = '' // 允许重复选择同一文件
}

async function onClearRestrictions() {
  if (!confirm('确定清空当前 AI 写作限制词文档？')) return
  importing.value = true
  try {
    const r = await clearWritingRestrictions(novelId)
    msg.value = r.message
    msgOk.value = true
    await load()
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  } finally {
    importing.value = false
  }
}

async function onImport(kind) {
  const text = importTexts[kind].trim()
  if (!text) {
    msg.value = '请先选择文件或粘贴内容'
    msgOk.value = false
    return
  }
  if (
    (kind === 'characters' || kind === 'restrictions') &&
    importMode.value === 'replace' &&
    ((kind === 'characters' && memory.value?.characters?.length) ||
      (kind === 'restrictions' && memory.value?.writing_restrictions?.has_text))
  ) {
    const target = kind === 'characters'
      ? `现有 ${memory.value.characters.length} 张人物卡`
      : `现有限制词文档（${memory.value.writing_restrictions.length} 字）`
    if (!confirm(`将以「替换」模式导入，${target}将被覆盖。继续？`)) return
  }
  importing.value = true
  try {
    const r = await importDoc(novelId, { kind, text, mode: importMode.value })
    msg.value = r.message
    msgOk.value = true
    importTexts[kind] = ''
    await load()
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  } finally {
    importing.value = false
  }
}

async function load() {
  try {
    memory.value = await getMemory(novelId)
    const cur = memory.value.volumes.find((v) => v.status === '连载中') || memory.value.volumes.at(-1)
    if (cur) selectVolume(cur)
  } catch (e) {
    msg.value = e.message
    msgOk.value = false
  }
}
onMounted(load)
</script>

<template>
  <div>
    <div class="novel-head">
      <button class="link" @click="router.push(`/novel/${novelId}`)">← 返回工作台</button>
      <h2>设定 / 记忆</h2>
      <span class="hint">人物卡、伏笔库、卷大纲与卷摘要会被自动注入 AI 写作的上下文中</span>
    </div>

    <div class="tabs">
      <div class="tab" :class="{ active: tab === 'characters' }" @click="tab = 'characters'">人物卡</div>
      <div class="tab" :class="{ active: tab === 'foreshadowings' }" @click="tab = 'foreshadowings'">伏笔库</div>
      <div class="tab" :class="{ active: tab === 'volume' }" @click="tab = 'volume'">卷管理 / 章摘要</div>
      <div class="tab" :class="{ active: tab === 'import' }" @click="tab = 'import'">📥 导入设定</div>
    </div>
    <p v-if="msg" class="msg" :class="msgOk ? 'ok' : 'err'">{{ msg }}</p>

    <!-- ============ 人物卡 ============ -->
    <template v-if="tab === 'characters' && memory">
      <div class="mem-grid">
        <aside class="card">
          <h3>角色列表</h3>
          <div v-for="c in memory.characters" :key="c.id" class="mem-item" @click="editCharacter(c)">
            <span>{{ c.name }}</span>
            <span class="tag">{{ c.role }}</span>
            <button class="mini-del" @click.stop="onDeleteCharacter(c)">×</button>
          </div>
          <p v-if="!memory.characters.length" class="hint">
            暂无人物卡。AI 定稿章节时会自动登记新角色；也可手工添加。
          </p>
          <button class="primary" style="margin-top: 10px" @click="newCharacter">＋ 新角色</button>
        </aside>

        <section class="card">
          <h3>{{ charForm.id ? `编辑：${charForm.name}` : '新角色' }}</h3>
          <div class="row2">
            <div>
              <label>角色名 *</label>
              <input v-model="charForm.name" placeholder="张三" />
            </div>
            <div>
              <label>身份</label>
              <select v-model="charForm.role">
                <option value="主角">主角</option>
                <option value="反派">反派</option>
                <option value="配角">配角</option>
              </select>
            </div>
          </div>
          <div v-for="k in CHAR_KEYS" :key="k">
            <label>{{ k }}</label>
            <input v-model="charForm.card[k]" :placeholder="`${k}（可留空）`" />
          </div>
          <div class="row">
            <button class="primary" @click="onSaveCharacter">保存人物卡</button>
            <button v-if="charForm.id" @click="newCharacter">取消</button>
          </div>
        </section>
      </div>
    </template>

    <!-- ============ 伏笔库 ============ -->
    <template v-if="tab === 'foreshadowings' && memory">
      <section class="card">
        <h3>{{ fForm.id ? `编辑伏笔：${fForm.title}` : '新伏笔' }}</h3>
        <div class="row2">
          <div>
            <label>伏笔标题 *</label>
            <input v-model="fForm.title" placeholder="如：F01 神秘玉佩" />
          </div>
          <div>
            <label>状态</label>
            <select v-model="fForm.status">
              <option v-for="s in FS_STATUS" :key="s" :value="s">{{ s }}</option>
            </select>
          </div>
        </div>
        <label>伏笔内容</label>
        <textarea v-model="fForm.description" rows="2" placeholder="埋设了什么信息，未来要如何揭晓"></textarea>
        <div class="row">
          <button class="primary" @click="onSaveForeshadowing">保存伏笔</button>
          <button v-if="fForm.id" @click="newForeshadowing">取消</button>
        </div>
      </section>

      <div class="f-list">
        <div v-for="f in memory.foreshadowings" :key="f.id" class="f-item" @click="editForeshadowing(f)">
          <div>
            <span class="badge" :class="f.status === '已回收' ? 'b-green' : f.status === '废弃' ? 'b-gray' : 'b-yellow'">
              {{ f.status }}
            </span>
            <b>{{ f.title }}</b>
          </div>
          <div class="hint">{{ f.description }}</div>
          <button class="mini-del" @click.stop="onDeleteForeshadowing(f)">×</button>
        </div>
        <p v-if="!memory.foreshadowings.length" class="hint">
          暂无伏笔。AI 定稿时会自动登记新埋伏笔；也可手工添加（如按你的规划编号 F01~F16）。
        </p>
      </div>
    </template>

    <!-- ============ 卷管理 / 章摘要 ============ -->
    <template v-if="tab === 'volume' && memory">
      <div class="shelf-head" style="margin-bottom: 10px">
        <h3 style="margin: 0">卷列表</h3>
        <div class="spacer"></div>
        <button class="primary" @click="openNewVolume">＋ 开新卷</button>
      </div>

      <div class="vol-grid">
        <div
          v-for="v in memory.volumes"
          :key="v.id"
          class="vol-item"
          :class="{ active: volumeForm.id === v.id }"
          @click="selectVolume(v)"
        >
          <div>
            <b>第{{ v.volume_no }}卷 {{ v.title }}</b>
            <span class="badge" :class="v.status === '连载中' ? 'b-yellow' : 'b-gray'">{{ v.status }}</span>
          </div>
          <div class="hint">
            {{ v.chapter_count }} 章{{ v.summary ? ' · 已有卷摘要' : ' · 未生成卷摘要' }}
          </div>
        </div>
      </div>

      <section v-if="volumeForm.id" class="card" style="margin-top: 14px">
        <h3>编辑：第 {{ memory.volumes.find((v) => v.id === volumeForm.id)?.volume_no }} 卷</h3>
        <div class="row2">
          <div>
            <label>卷名</label>
            <input v-model="volumeForm.title" />
          </div>
          <div>
            <label>状态</label>
            <select v-model="volumeForm.status">
              <option value="连载中">连载中</option>
              <option value="完结">完结</option>
            </select>
          </div>
        </div>
        <label>卷大纲（细纲师规划每章的总依据）</label>
        <textarea v-model="volumeForm.outline" rows="8" placeholder="如：本卷围绕「宗门大比」展开：1-5 章报名与暗流 → 6-10 章初赛黑马 → 11-15 章决赛对手使诈 → 16-18 章揭穿阴谋夺冠 → 卷末钩子：神秘长老现身"></textarea>
        <label>卷摘要（由 AI 汇总本卷各章摘要生成）</label>
        <div v-if="volumeForm.summary" class="summary-box">{{ volumeForm.summary }}</div>
        <p v-else class="hint">未生成。章节定稿后点「✨ AI 生成卷摘要」。</p>
        <div class="row">
          <button class="primary" @click="onSaveVolume">保存卷</button>
          <button :disabled="genningOutline" @click="onGenVolumeOutline">
            {{ genningOutline ? '生成中…' : '✨ AI 生成卷大纲（重写）' }}
          </button>
          <button :disabled="genningSummary" @click="onGenVolumeSummary">
            {{ genningSummary ? '汇总中…' : '✨ AI 生成卷摘要' }}
          </button>
        </div>
      </section>

      <h3 style="margin: 20px 0 4px">章摘要（由总结师逐章生成）</h3>
      <div class="summary-card" v-for="s in memory.summaries" :key="s.chapter_no">
        <div>
          <b>第{{ s.chapter_no }}章 {{ s.chapter_title }}</b>
          <span class="hint">{{ fmtTime(s.created_at) }}</span>
        </div>
        <div class="hint" v-if="s.outline_progress">大纲进度：{{ s.outline_progress }}</div>
        <div>{{ s.summary }}</div>
        <div class="tags" v-if="s.key_events?.length">
          <span v-for="(ev, i) in s.key_events" :key="i" class="tag">{{ ev }}</span>
        </div>
      </div>
      <p v-if="!memory.summaries.length" class="hint">暂无摘要。在工作台对章节点「📝 定稿（更新记忆）」后生成。</p>

      <!-- 开新卷弹窗 -->
      <div v-if="showNewVolume" class="overlay" @click.self="showNewVolume = false">
        <div class="modal">
          <h3>开新卷</h3>
          <p class="hint">创建后上一卷将自动标记为「完结」，新章节默认写入新卷</p>
          <label>卷名</label>
          <input v-model="newVolForm.title" />
          <label>卷大纲（可先 AI 生成再修改）</label>
          <textarea v-model="newVolForm.outline" rows="6" placeholder="AI 会根据全书简介、上一卷摘要与待回收伏笔生成本卷大纲"></textarea>
          <div class="row">
            <button :disabled="genningOutline" @click="onGenVolumeOutline">
              {{ genningOutline ? '生成中…' : '✨ AI 生成卷大纲' }}
            </button>
          </div>
          <div class="row">
            <button class="primary" :disabled="creatingVol" @click="onCreateVolume">
              {{ creatingVol ? '创建中…' : '创建新卷' }}
            </button>
            <button @click="showNewVolume = false">取消</button>
          </div>
        </div>
      </div>
    </template>

    <!-- ============ 导入设定 ============ -->
    <template v-if="tab === 'import'">
      <div class="import-grid">
        <section class="card">
          <h3>📖 导入故事圣经</h3>
          <p class="hint">
            整篇作为「设定铁律」注入写手/校对/细纲师每次生成；自动同步书名/题材/风格/简介/目标字数
          </p>
          <input type="file" accept=".md,.txt" @change="onFile($event, 'bible')" />
          <textarea v-model="importTexts.bible" rows="8" placeholder="选择或粘贴 00-故事圣经.md 全文"></textarea>
          <div class="row">
            <button class="primary" :disabled="importing" @click="onImport('bible')">导入故事圣经</button>
          </div>
        </section>

        <section class="card">
          <h3>🗺 导入故事大纲</h3>
          <p class="hint">
            自动按「### 卷X」建立分卷结构并填充各卷大纲（卷一连载中、其余未开始）；「全书总纲」作为硬性红线注入细纲师；「小说简介」同步为简介
          </p>
          <input type="file" accept=".md,.txt" @change="onFile($event, 'outline')" />
          <textarea v-model="importTexts.outline" rows="8" placeholder="选择或粘贴 02-故事大纲.md 全文"></textarea>
          <div class="row">
            <button class="primary" :disabled="importing" @click="onImport('outline')">导入故事大纲</button>
          </div>
        </section>

        <section class="card">
          <h3>👥 导入人物卡</h3>
          <p class="hint">
            按「## N. 角色名」解析每张卡（身份自动识别主角/反派），整卡原文保留为人设约束注入写手上下文
          </p>
          <input type="file" accept=".md,.txt" @change="onFile($event, 'characters')" />
          <textarea v-model="importTexts.characters" rows="8" placeholder="选择或粘贴 01-人物卡.md 全文"></textarea>
          <label>导入模式</label>
          <select v-model="importMode">
            <option value="replace">替换现有全部人物卡</option>
            <option value="append">追加（同名覆盖）</option>
          </select>
          <div class="row">
            <button class="primary" :disabled="importing" @click="onImport('characters')">
              {{ importing ? '导入中…' : '导入人物卡' }}
            </button>
          </div>
        </section>

        <section class="card">
          <h3>✍️ 导入 AI 写作限制词</h3>
          <p class="hint">
            约束写手、修稿和校对的表达方式，减少模板化词汇与句式；不改变故事设定，也不能替代人工审稿。
          </p>
          <p class="hint" v-if="memory?.writing_restrictions?.has_text">
            当前已保存 {{ memory.writing_restrictions.length }} 字；超长文档仅在注入模型时保留首尾部分。
          </p>
          <input type="file" accept=".md,.txt" @change="onFile($event, 'restrictions')" />
          <textarea v-model="importTexts.restrictions" rows="8" placeholder="选择或粘贴限制词、禁用词和自检规则文档"></textarea>
          <label>导入模式</label>
          <select v-model="importMode">
            <option value="replace">替换现有限制词文档</option>
            <option value="append">追加到现有文档</option>
          </select>
          <div class="row">
            <button class="primary" :disabled="importing" @click="onImport('restrictions')">
              {{ importing ? '导入中…' : '导入限制词文档' }}
            </button>
            <button
              v-if="memory?.writing_restrictions?.has_text"
              class="danger"
              :disabled="importing"
              @click="onClearRestrictions"
            >清空</button>
          </div>
        </section>
      </div>
      <p v-if="msg && tab === 'import'" class="msg" :class="msgOk ? 'ok' : 'err'">{{ msg }}</p>
    </template>
  </div>
</template>
