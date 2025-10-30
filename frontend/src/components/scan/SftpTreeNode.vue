#SftpTreeNode.vue
<template>
  <li :style="{ paddingLeft: `${level * 16}px` }" class="select-none">
    <div
      class="flex items-center gap-2 py-1 px-2 rounded cursor-pointer"
      :class="selectedPath === path ? 'bg-black/5 dark:bg-white/10' : 'hover:bg-black/5 dark:hover:bg-white/10'"
      @click="onChoose"
      @dblclick="toggle"
    >
      <!-- Toggle -->
      <button
        v-if="isDir"
        class="w-5 text-xs opacity-70 hover:opacity-100"
        @click.stop="toggle"
        :title="expanded ? 'Zuklappen' : 'Aufklappen'"
      >
        {{ expanded ? '▾' : '▸' }}
      </button>
      <span v-else class="w-5"></span>

      <!-- Icon -->
      <span aria-hidden="true">{{ isDir ? '📁' : '📄' }}</span>

      <!-- Name (klick = Auswahl) -->
      <span class="truncate">{{ name }}</span>

      <!-- Quick action rechts -->
      
    </div>

    <!-- Children -->
    <ul v-if="isDir && expanded && children?.length">
      <SftpTreeNode
        v-for="c in childrenSorted"
        :key="c.path"
        :sid="sid"
        :path="c.path"
        :name="c.name"
        :type="c.type"
        :level="level + 1"
        :load-children="loadChildren"
        :children-map="childrenMap"
        :expanded-set="expandedSet"
        :selected-path="selectedPath"
        @choose="$emit('choose', $event)"
      />
    </ul>
  </li>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SftpEntry } from '@/api'

const props = defineProps<{
  sid: string
  path: string
  name: string
  type?: 'dir' | 'file'
  level: number
  loadChildren: (path: string, expand?: boolean) => Promise<void> | void
  childrenMap: Record<string, SftpEntry[]>
  expandedSet: Set<string>
  selectedPath: string
}>()

const emit = defineEmits<{ (e: 'choose', path: string): void }>()

// decide using explicit type; root is a dir
const isDir = computed(() =>
  props.type ? props.type === 'dir' : props.path === '/'
)

const expanded = computed({
  get: () => props.expandedSet.has(props.path),
  set: v => { v ? props.expandedSet.add(props.path) : props.expandedSet.delete(props.path) }
})

const children = computed(() => props.childrenMap[props.path] || [])
const childrenSorted = computed(() =>
  [...children.value].sort((a, b) =>
    a.type === b.type ? a.name.localeCompare(b.name) : a.type === 'dir' ? -1 : 1
  )
)

async function toggle() {
  if (!isDir.value) return
  if (!expanded.value) await props.loadChildren(props.path, true)
  else expanded.value = false
}

function onChoose() {
  emit('choose', props.path)
}
</script>
