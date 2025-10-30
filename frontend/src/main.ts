import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './style.css'

const theme = localStorage.getItem('sf_theme') || 'light'
document.documentElement.classList.toggle('dark', theme === 'dark')

createApp(App).use(createPinia()).use(router).mount('#app')
