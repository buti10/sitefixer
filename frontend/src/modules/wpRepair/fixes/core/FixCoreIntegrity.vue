<!-- src/modules/wpRepair/fixes/core/FixCoreIntegrity.vue -->
<script setup lang="ts">
import { ref } from "vue";
import FixCard from "../../components/FixCard.vue";
import { getFix } from "../registry";

const fix = getFix("core_preview");
const params = ref({ max_files: 500 });
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-center gap-3">
      <label class="text-sm text-slate-600 dark:text-slate-300">max_files</label>
      <input v-model.number="params.max_files" type="number" min="1" class="w-28 rounded-lg border px-3 py-2 text-sm dark:bg-slate-900" />
    </div>
    <FixCard :fix="fix" :params="params" />
  </div>
</template>
