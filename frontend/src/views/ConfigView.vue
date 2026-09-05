<script setup>
import { onMounted, reactive, ref } from 'vue'
import { getConfig, saveConfig, testConnection } from '../api'

const config = reactive({ base_url: '', api_key: '', model_name: '', temperature: 0.8 })
const saved = reactive({ has_key: false, key_tail: '' })
const configMsg = ref('')
const configOk = ref(false)
const testing = ref(false)
const saving = ref(false)

onMounted(async () => {
  try {
    const c = await getConfig()
    config.base_url = c.base_url
    config.model_name = c.model_name
    config.temperature = c.temperature
    saved.has_key = c.has_key
    saved.key_tail = c.key_tail
  } catch (e) {
    configMsg.value = e.message
  }
})

async function onSaveConfig() {
  saving.value = true
  configMsg.value = ''
  configOk.value = false
  try {
    const c = await saveConfig({ ...config, context_window: 64000 })
    saved.has_key = c.has_key
    saved.key_tail = c.key_tail
    config.api_key = ''
    configMsg.value = '已保存'
    configOk.value = true
  } catch (e) {
    configMsg.value = e.message
  } finally {
    saving.value = false
  }
}

async function onTest() {
  testing.value = true
  configMsg.value = ''
  configOk.value = false
  try {
    const r = await testConnection()
    configOk.value = r.ok
    configMsg.value = r.ok
      ? `连接正常：模型回复「${r.reply}」，耗时 ${r.latency_ms} ms`
      : r.error
  } catch (e) {
    configMsg.value = e.message
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <div class="narrow">
    <div class="shelf-head">
      <h2>API 配置</h2>
      <span class="hint">支持任意 OpenAI 兼容接口（DeepSeek / Kimi / 豆包 / 通义 / GLM…）</span>
    </div>
    <section class="card">
      <label>Base URL</label>
      <input v-model="config.base_url" placeholder="https://api.deepseek.com/v1" />

      <label>
        API Key
        <span v-if="saved.has_key" class="hint">已保存：尾号 {{ saved.key_tail }}</span>
      </label>
      <input v-model="config.api_key" type="password" placeholder="sk-..." />

      <label>模型名</label>
      <input v-model="config.model_name" placeholder="deepseek-chat" />

      <label>温度（0~2，写作建议 0.8）</label>
      <input v-model.number="config.temperature" type="number" min="0" max="2" step="0.1" />

      <div class="row">
        <button class="primary" :disabled="saving" @click="onSaveConfig">
          {{ saving ? '保存中…' : '保存配置' }}
        </button>
        <button :disabled="testing" @click="onTest">
          {{ testing ? '测试中…' : '测试连接' }}
        </button>
      </div>
      <p v-if="configMsg" class="msg" :class="configOk ? 'ok' : 'err'">{{ configMsg }}</p>
    </section>
  </div>
</template>
