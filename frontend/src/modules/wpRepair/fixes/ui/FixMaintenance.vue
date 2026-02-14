<!-- src/modules/wpRepair/fixes/ui/FixMaintenance.vue -->
<script setup lang="ts">
import FixCard from "../../components/FixCard.vue";
import { getFix } from "../fixRegistry";

const fix = getFix("maintenance_remove");
</script>

<template>
  <FixCard :fix="fix" />
</template>
