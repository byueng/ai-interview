import { createRouter, createWebHashHistory } from 'vue-router'
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('./views/HomeView.vue'), meta: { title: '序厅' } },
    { path: '/settings', name: 'settings', component: () => import('./views/SettingsView.vue'), meta: { title: '面试准备' } },
    { path: '/interview', name: 'interview', component: () => import('./views/InterviewView.vue'), meta: { title: '面试室' } },
    { path: '/stories/:slug?', name: 'stories', component: () => import('./views/StoriesView.vue'), meta: { title: '人物志' } },
    { path: '/review', name: 'review', component: () => import('./views/ReviewView.vue'), meta: { title: '本次回顾' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0, behavior: 'instant' }),
})
router.afterEach(to => { document.title = `${to.meta.title} · ai-interview` })
