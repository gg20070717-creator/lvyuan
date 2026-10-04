<template>
  <img :src="landscape" class="guofeng-landscape" alt="" aria-hidden="true" draggable="false" />
</template>

<script setup lang="ts">
import landscape from '@/assets/guofeng-landscape.svg'
</script>

<style scoped>
.guofeng-landscape { display: block; pointer-events: none; user-select: none; object-fit: contain; }
</style>
