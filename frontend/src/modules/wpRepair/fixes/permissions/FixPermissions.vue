<!-- src/modules/wpRepair/fixes/permissions/FixPermissions.vue -->
<script setup lang="ts">
import FixCard from "../../components/FixCard.vue";
import { getFix } from "../registry";

const fix = getFix("permissions_apply");
</script>

<template>
  <FixCard :fix="fix" />
</template>
