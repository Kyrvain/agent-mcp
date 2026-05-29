import { createRouter, createWebHistory } from 'vue-router'
import CrawlPage from '../views/CrawlPage.vue'
import RunDetailPage from '../views/RunDetailPage.vue'
import RunsPage from '../views/RunsPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: CrawlPage },
    { path: '/runs', component: RunsPage },
    { path: '/runs/:id', component: RunDetailPage, props: true },
  ],
})
