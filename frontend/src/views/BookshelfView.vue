<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createNovel, deleteNovel, listNovels } from '../api'
import { fmtTime } from '../utils'

const router = useRouter()
const novels = ref([])
const loading = ref(true)
const showCreate = ref(false)
const errMsg = ref('')
const form = reactive({
  title: '',
  genre: '',
  style: '',
  protagonist: '',
  world_setting: '',
  synopsis: '',
  target_word_count: 0,
})

async function load() {
  loading.value = true
  errMsg.value = ''
  try {
    novels.value = await listNovels()
  } catch (e) {
    errMsg.value = e.message
  } finally {
    loading.value = false
  }
}
onMounted(load)

function openCreate() {
  Object.keys(form).forEach((k) => (form[k] = k === 'target_word_count' ? 0 : ''))
  errMsg.value = ''
  showCreate.value = true
}

async function onCreate() {
  errMsg.value = ''
  if (!form.title.trim()) {
    errMsg.value = '请填写书名'
    return
  }
  try {
    const n = await createNovel({ ...form, target_word_count: Number(form.target_word_count) || 0 })
    showCreate.value = false
    router.push(`/novel/${n.id}`)
  } catch (e) {
    errMsg.value = e.message
  }
}

async function onDelete(n) {
  if (!confirm(`确定删除《${n.title}》？所有章节将一并删除，不可恢复。`)) return
  try {
    await deleteNovel(n.id)
    load()
  } catch (e) {
    errMsg.value = e.message
  }
}
</script>

<template>
  <div>
    <div class="shelf-head">
      <h2>书架</h2>
      <div class="spacer"></div>
      <button class="primary" @click="openCreate">＋ 新建小说</button>
    </div>

    <p v-if="errMsg" class="msg err">{{ errMsg }}</p>
    <p v-if="loading" class="hint">加载中…</p>
    <p v-else-if="!novels.length" class="hint">
      书架空空如也。点击「新建小说」创建第一本书，填入设定后即可开始 AI 写作。
    </p>

    <div v-else class="shelf-grid">
      <div
        v-for="n in novels"
        :key="n.id"
        class="novel-card"
        @click="router.push(`/novel/${n.id}`)"
      >
        <button class="card-del" title="删除" @click.stop="onDelete(n)">×</button>
        <h3>{{ n.title }}</h3>
        <div class="tags">
          <span v-if="n.genre" class="tag">{{ n.genre }}</span>
          <span v-if="n.style" class="tag">{{ n.style }}</span>
        </div>
        <p class="hint">{{ n.chapter_count }} 章 · {{ n.status }} · 更新于 {{ fmtTime(n.updated_at) }}</p>
      </div>
    </div>

    <!-- 新建小说弹窗 -->
    <div v-if="showCreate" class="overlay" @click.self="showCreate = false">
      <div class="modal">
        <h3>新建小说</h3>
        <label>书名 *</label>
        <input v-model="form.title" placeholder="凡人修仙传" />
        <div class="row2">
          <div>
            <label>题材</label>
            <input v-model="form.genre" placeholder="玄幻 / 都市 / 科幻" />
          </div>
          <div>
            <label>风格</label>
            <input v-model="form.style" placeholder="轻松幽默 / 热血 / 悬疑" />
          </div>
        </div>
        <div class="row2">
          <div>
            <label>主角</label>
            <input v-model="form.protagonist" placeholder="主角名" />
          </div>
          <div>
            <label>目标字数（可选）</label>
            <input v-model.number="form.target_word_count" type="number" min="0" placeholder="500000" />
          </div>
        </div>
        <label>世界观设定</label>
        <textarea v-model="form.world_setting" rows="2" placeholder="如：修仙界，练气→筑基→金丹"></textarea>
        <label>内容简介</label>
        <textarea v-model="form.synopsis" rows="2" placeholder="一句话故事主线，AI 会据此把控剧情方向"></textarea>
        <p v-if="errMsg" class="msg err">{{ errMsg }}</p>
        <div class="row">
          <button class="primary" @click="onCreate">创建</button>
          <button @click="showCreate = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>
