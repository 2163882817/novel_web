import { createRouter, createWebHistory } from 'vue-router'
import BookshelfView from './views/BookshelfView.vue'
import NovelView from './views/NovelView.vue'
import NovelSettingsView from './views/NovelSettingsView.vue'
import ConfigView from './views/ConfigView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'shelf', component: BookshelfView },
    { path: '/novel/:id', name: 'novel', component: NovelView },
    { path: '/novel/:id/settings', name: 'novel-settings', component: NovelSettingsView },
    { path: '/config', name: 'config', component: ConfigView },
  ],
})
