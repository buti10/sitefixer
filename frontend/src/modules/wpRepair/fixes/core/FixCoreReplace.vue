<!-- src/modules/wpRepair/fixes/core/FixCoreReplace.vue -->
<script setup lang="ts">
import { ref } from "vue";
import FixCard from "../../components/FixCard.vue";
import { getFix } from "../registry";

const fix = getFix("core_replace_apply");
const params = ref({
  max_files: 500,
  max_replace: 50,
  allow_changed: true,
  allow_missing: false,
});
</script>

<template>
  <div class="space-y-4">
    <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
      <div>
        <label class="block text-xs text-slate-500 mb-1">max_files</label>
        <input v-model.number="params.max_files" type="number" min="1" class="w-full rounded-lg border px-3 py-2 text-sm dark:bg-slate-900" />
      </div>
      <div>
        <label class="block text-xs text-slate-500 mb-1">max_replace</label>
        <input v-model.number="params.max_replace" type="number" min="1" class="w-full rounded-lg border px-3 py-2 text-sm dark:bg-slate-900" />
      </div>
      <div class="flex items-center gap-2 pt-6">
        <input id="allow_changed" v-model="params.allow_changed" type="checkbox" class="h-4 w-4" />
        <label for="allow_changed" class="text-sm">allow_changed</label>
      </div>
      <div class="flex items-center gap-2 pt-6">
        <input id="allow_missing" v-model="params.allow_missing" type="checkbox" class="h-4 w-4" />
        <label for="allow_missing" class="text-sm">allow_missing</label>
      </div>
    </div>

    <FixCard :fix="fix" :params="params" />
  </div>
</template>
