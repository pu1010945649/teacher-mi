import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/login', component: () => import('../views/Login.vue') },
  {
    path: '/teacher',
    component: () => import('../layouts/TeacherLayout.vue'),
    meta: { role: 'teacher' },
    children: [
      { path: '', redirect: '/teacher/students' },
      { path: 'students', component: () => import('../views/teacher/Students.vue') },
      { path: 'assignments', component: () => import('../views/teacher/Assignments.vue') },
      { path: 'grading', component: () => import('../views/teacher/Grading.vue') },
      { path: 'worksheets', component: () => import('../views/teacher/Worksheets.vue') },
      { path: 'schedule', component: () => import('../views/teacher/Schedule.vue') },
      { path: 'ai-settings', component: () => import('../views/teacher/AiSettings.vue') },
    ],
  },
  {
    path: '/student',
    component: () => import('../layouts/StudentLayout.vue'),
    meta: { role: 'student' },
    children: [
      { path: '', redirect: '/student/assignments' },
      { path: 'assignments', component: () => import('../views/student/Assignments.vue') },
      { path: 'worksheets', component: () => import('../views/student/Worksheets.vue') },
      { path: 'schedule', component: () => import('../views/student/Schedule.vue') },
    ],
  },
  { path: '/', redirect: '/login' },
  { path: '/:pathMatch(.*)*', redirect: '/login' },
]

const router = createRouter({ history: createWebHashHistory(), routes })

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  const role = localStorage.getItem('role')
  if (to.path !== '/login' && !token) return '/login'
  if (to.meta.role && role !== to.meta.role) return role === 'teacher' ? '/teacher' : role === 'student' ? '/student' : '/login'
  if (to.path === '/login' && token) return role === 'teacher' ? '/teacher' : '/student'
})

export default router
