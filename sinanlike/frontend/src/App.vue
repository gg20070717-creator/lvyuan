<template>
  <router-view v-slot="{ Component }">
    <Transition name="page-entry" mode="out-in">
      <component :is="Component" />
    </Transition>
  </router-view>
</template>

<script setup lang="ts">
// 欢迎页与首页之间延续同样的轻柔过渡。
</script>

<style>
.page-entry-enter-active, .page-entry-leave-active { transition: opacity .25s ease; }
.page-entry-enter-from, .page-entry-leave-to { opacity: 0; }
@media (prefers-reduced-motion: reduce) { .page-entry-enter-active, .page-entry-leave-active { transition: none; } }
</style>
