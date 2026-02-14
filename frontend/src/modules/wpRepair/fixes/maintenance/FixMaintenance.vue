<!-- src/modules/wpRepair/fixes/maintenance/FixMaintenance.vue -->
<script setup lang="ts">
import FixCard from "../../components/FixCard.vue";
import { getFix } from "../registry";

const fix = getFix("maintenance_remove");
</script>

<template>
  <FixCard :fix="fix" />
</template>
