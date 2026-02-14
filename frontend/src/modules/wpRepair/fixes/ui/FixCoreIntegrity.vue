<!-- src/modules/wpRepair/fixes/ui/FixCoreIntegrity.vue -->
<script setup lang="ts">
import { ref } from "vue";
import FixCard from "../../components/FixCard.vue";
import { getFix } from "../fixRegistry";

const fix = getFix("core_preview");
const maxFiles = ref<number>(500);
</script>

<template>
  <FixCard :fix="fix" :params="{ max_files: maxFiles }">
    <template #params>
      <div class="flex items-center gap-2">
        <label class="text-xs text-slate-600 dark:text-slate-300">max_files</label>
        <input
          v-model.number="maxFiles"
          type="number"
          min="100"
          step="100"
          class="w-28 px-3 py-2 rounded-md border border-black/10 dark:border-white/10 bg-white dark:bg-[#0b1020] text-sm"
        />
      </div>
    </template>
  </FixCard>
</template>
