import { createRouter, createWebHistory } from 'vue-router';
import HomeView from './views/HomeView.vue';
import ReaderView from './views/ReaderView.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/jobs/:id', component: ReaderView },
  ],
});

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('auth_token');
  if (!token && to.path !== '/') {
    next('/');
  } else {
    next();
  }
});