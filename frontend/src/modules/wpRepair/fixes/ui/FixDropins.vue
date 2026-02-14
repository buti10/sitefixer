<!-- src/modules/wpRepair/fixes/ui/FixDropins.vue -->
<script setup lang="ts">
import { computed, ref } from "vue";
import FixCard from "../../components/FixCard.vue";
import { getFix } from "../fixRegistry";

const fix = getFix("dropins_apply");
const dropinsInput = ref<string>("object-cache.php");

const dropins = computed(() => {
  const raw = (dropinsInput.value || "").trim();
  if (!raw) return [];
  return raw
    .split(/[\n,]/)
    .map((s) => s.trim())
    .filter(Boolean);
});
</script>

<template>
  <FixCard :fix="fix" :params="{ dropins }">
    <template #params>
      <div class="space-y-2">
        <div class="text-xs opacity-70">
          Kommagetrennt oder eine Datei pro Zeile
        </div>
        <textarea
          v-model="dropinsInput"
          class="px-3 py-2 rounded-md border border-black/10 dark:border-white/10 bg-white dark:bg-[#0b1020] text-sm w-full min-h-[3rem]"
          placeholder="object-cache.php, advanced-cache.php"
        />
      </div>
    </template>
  </FixCard>
</template>
