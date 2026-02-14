<!-- src/modules/wpRepair/fixes/dropins/FixDropins.vue -->
<script setup lang="ts">
import FixCard from "../../components/FixCard.vue";
import { getFix } from "../registry";

const fix = getFix("dropins_apply");
</script>

<template>
  <FixCard :fix="fix" />
</template>
