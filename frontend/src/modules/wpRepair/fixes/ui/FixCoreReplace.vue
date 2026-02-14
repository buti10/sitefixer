<!-- src/modules/wpRepair/fixes/ui/FixCoreReplace.vue -->
<script setup lang="ts">
import { ref } from "vue";
import FixCard from "../../components/FixCard.vue";
import { getFix } from "../fixRegistry";

const fix = getFix("core_replace_apply");

const maxFiles = ref<number>(500);
const maxReplace = ref<number>(50);
const allowChanged = ref<boolean>(true);
const allowMissing = ref<boolean>(false);

const params = {
  max_files: maxFiles,
  max_replace: maxReplace,
  allow_changed: allowChanged,
  allow_missing: allowMissing,
};
</script>

<template>
  <FixCard :fix="fix" :params="params">
    <template #params>
      <div class="grid gap-3 md:grid-cols-4">
        <div class="rounded-md border border-black/5 dark:border-white/10 p-3">
          <div class="text-xs opacity-70">max_files</div>
          <input
            v-model.number="maxFiles"
            type="number"
            min="100"
            step="100"
            class="mt-1 w-full px-3 py-2 rounded-md border border-black/10 dark:border-white/10 bg-white dark:bg-[#0b1020] text-sm"
          />
        </div>

        <div class="rounded-md border border-black/5 dark:border-white/10 p-3">
          <div class="text-xs opacity-70">max_replace</div>
          <input
            v-model.number="maxReplace"
            type="number"
            min="1"
            step="1"
            class="mt-1 w-full px-3 py-2 rounded-md border border-black/10 dark:border-white/10 bg-white dark:bg-[#0b1020] text-sm"
          />
        </div>

        <label class="rounded-md border border-black/5 dark:border-white/10 p-3 flex items-center gap-2">
          <input type="checkbox" v-model="allowChanged" />
          <span class="text-sm">allow_changed</span>
        </label>

        <label class="rounded-md border border-black/5 dark:border-white/10 p-3 flex items-center gap-2">
          <input type="checkbox" v-model="allowMissing" />
          <span class="text-sm">allow_missing</span>
        </label>
      </div>
    </template>
  </FixCard>
</template>
