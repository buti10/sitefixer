<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue'
import { useMailStore } from '@/modules/comms-mail/stores/MailStore'
const mail = useMailStore()
let t:number|undefined
onMounted(async () => { await mail.fetchUnread(); t = window.setInterval(()=>mail.fetchUnread(), 60000) })
onBeforeUnmount(() => { if (t) clearInterval(t) })
</script>
<template><span class="hidden"/></template>
