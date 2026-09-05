<script setup>
</script>

<template>
  <div class="page">
    <header class="topbar">
      <h1>AI 网文写作台</h1>
      <nav class="nav">
        <router-link to="/">书架</router-link>
        <router-link to="/config">API 配置</router-link>
      </nav>
    </header>
    <router-view />
  </div>
</template>
