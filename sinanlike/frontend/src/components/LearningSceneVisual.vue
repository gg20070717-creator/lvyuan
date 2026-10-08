<template>
  <div class="learning-scene-visual" :class="`visual-${kind}`" aria-hidden="true">
    <svg viewBox="0 0 340 190" fill="none" stroke-linecap="round" stroke-linejoin="round">
      <path class="cloud" d="M269 40h31c9 0 9-12 1-12-1-10-16-13-21-3-8-3-14 4-11 10M273 47h36M34 156h29c8 0 9-11 1-12-2-10-16-12-20-3-8-2-13 4-10 10M39 163h33" />
      <path class="ground" d="M99 177h143M115 183h110" />
      <g v-if="kind === 'diagnostic'">
        <rect class="soft" x="107" y="35" width="116" height="132" rx="11" transform="rotate(-8 107 35)" />
        <path class="paper" d="M130 19h87l16 16v123a9 9 0 0 1-9 9h-94a9 9 0 0 1-9-9V28a9 9 0 0 1 9-9Z" />
        <path class="detail" d="M216 20v18h17M138 45h49M138 53h31M157 77h51M157 100h44M157 123h51" />
        <circle class="ink" cx="144" cy="77" r="5" /><circle class="detail" cx="144" cy="100" r="5" /><circle class="detail" cx="144" cy="123" r="5" />
        <circle class="accent" cx="144" cy="77" r="2" />
        <rect class="paper" x="211" y="116" width="43" height="40" rx="10" />
        <path class="ink" d="m222 137 7 7 14-16" />
        <rect class="soft" x="78" y="56" width="35" height="36" rx="9" />
        <path class="ink" d="M87 65h8q5 0 5 4v16q-2-3-5-3h-8V65ZM100 69h5v16h-5" />
        <path class="corner" d="M129 32v-5h7M222 150v8h-8" />
      </g>
      <g v-else-if="kind === 'plan'">
        <path class="paper" d="m74 46 61-17 69 16 59-18v117l-59 18-69-16-61 17V46Z" />
        <path class="detail" d="M135 30v116M204 46v115M88 66l29-8M216 65l32-9M148 136l34 7" />
        <path class="route" d="M101 121c32-5 20-48 57-48s13 59 56 46c15-5 14-25 26-29" />
        <circle class="soft" cx="101" cy="121" r="8" /><circle class="ink" cx="101" cy="121" r="3" />
        <circle class="paper" cx="168" cy="87" r="12" /><path class="ink" d="m163 87 4 4 7-9" />
        <path class="paper" d="M240 52a16 16 0 0 1 16 16c0 14-16 26-16 26s-16-12-16-26a16 16 0 0 1 16-16Z" /><circle class="ink" cx="240" cy="68" r="5" />
        <path class="corner" d="m82 52 8-2M252 132v7l-8 2" />
      </g>
      <g v-else-if="kind === 'communication' || kind === 'narrate'">
        <path class="paper" d="M93 37h111a13 13 0 0 1 13 13v58a13 13 0 0 1-13 13h-66l-23 19v-19H93a13 13 0 0 1-13-13V50a13 13 0 0 1 13-13Z" />
        <path class="detail" d="M102 63h79M102 77h54" />
        <path class="soft" d="M178 88h75a12 12 0 0 1 12 12v42a12 12 0 0 1-12 12h-10v16l-19-16h-46a12 12 0 0 1-12-12v-42a12 12 0 0 1 12-12Z" />
        <circle class="accent" cx="189" cy="120" r="3" /><circle class="accent" cx="215" cy="120" r="3" /><circle class="accent" cx="241" cy="120" r="3" />
        <rect class="paper" x="51" y="105" width="34" height="49" rx="8" />
        <path v-if="kind === 'communication'" class="ink" d="M62 117c-4 10 1 18 13 23l3-6-5-3-3 3c-4-2-6-5-7-9l3-2-1-6h-3Z" />
        <g v-else class="ink"><rect x="63" y="114" width="10" height="17" rx="5" /><path d="M59 127a9 9 0 0 0 18 0M68 136v6M63 143h10" /></g>
        <path class="corner" d="M90 54v-7h8M251 137v7h-7" />
      </g>
      <g v-else-if="kind === 'emergency'">
        <path class="detail" d="M94 78H57v40h34M235 76h43v45h-41M170 146v20" />
        <rect class="paper" x="38" y="56" width="44" height="39" rx="10" /><rect class="paper" x="258" y="101" width="44" height="39" rx="10" />
        <path class="ink" d="m60 65 11 21H49l11-21ZM60 73v5M60 82h.1M270 121l6 6 13-15" />
        <path class="soft" d="m170 26 60 22v42c0 30-25 51-60 66-35-15-60-36-60-66V48l60-22Z" />
        <path class="paper" d="m170 42 43 16v32c0 20-18 36-43 49-25-13-43-29-43-49V58l43-16Z" />
        <path class="ink" d="m151 89 13 13 27-30" />
        <path class="corner" d="M116 56v-6l8-3M224 84v8" />
        <circle class="accent" cx="91" cy="118" r="3" /><circle class="accent" cx="237" cy="76" r="3" />
      </g>
      <g v-else-if="kind === 'pre'">
        <path class="paper" d="m101 65 47-13 53 13 40-13v100l-40 12-53-12-47 12V65Z" />
        <path class="detail" d="M148 53v99M201 65v99" />
        <path class="route" d="M121 135c26-2 17-35 41-35s18 31 39 21c12-6 14-22 24-30" />
        <circle class="ink" cx="121" cy="135" r="4" /><circle class="paper" cx="201" cy="121" r="6" />
        <path class="soft" d="M222 31a17 17 0 0 1 17 17c0 15-17 28-17 28s-17-13-17-28a17 17 0 0 1 17-17Z" /><circle class="ink" cx="222" cy="48" r="5" />
        <rect class="paper" x="67" y="36" width="70" height="60" rx="9" /><path class="ink" d="M79 51h12M79 61h32M79 71h24" />
        <path class="corner" d="M75 47v-4h6M231 139v7l-7 2" />
        <path class="detail" d="M254 86h23M260 93h24" />
      </g>
      <g v-else-if="kind === 'mid'">
        <path class="route" d="M65 130c22-33 73 32 118 9 29-14 39-45 78-38" />
        <path class="paper" d="M122 89h87v69h-87V89Z" />
        <path class="soft" d="M114 89c21-5 36-14 51-30 16 16 31 25 52 30h-103Z" />
        <path class="ink" d="M118 94h95M135 102v49M195 102v49M155 158v-29a10 10 0 0 1 20 0v29M111 159h108M113 165h103" />
        <path class="detail" d="M147 82h36M127 113h13M190 113h13" />
        <path class="paper" d="M245 47a16 16 0 0 1 16 16c0 14-16 25-16 25s-16-11-16-25a16 16 0 0 1 16-16Z" /><circle class="ink" cx="245" cy="63" r="5" />
        <rect class="paper" x="63" y="63" width="40" height="39" rx="10" /><path class="ink" d="m72 84 23-13-8 24-5-9-10-2ZM82 86l5-5" />
        <circle class="accent" cx="65" cy="130" r="4" /><path class="corner" d="M127 96v-4h6M203 145v7h-7" />
      </g>
      <g v-else>
        <path class="soft" d="M125 35h96v128h-96V35Z" />
        <rect class="paper" x="107" y="26" width="96" height="136" rx="9" />
        <path class="ink" d="M126 48h50M134 73h42M134 96h31M134 120h42M121 70l4 4 6-7M121 93l4 4 6-7M121 117l4 4 6-7" />
        <path class="detail" d="M121 138h55M220 51c27 5 31 41 8 55M77 127c-25-10-22-46-1-56" />
        <path class="ink" d="m222 98 6 8 9-4M70 70l7 1-1 8" />
        <rect class="paper" x="192" y="111" width="43" height="40" rx="10" /><path class="ink" d="m204 133 7 7 13-18" />
        <path class="corner" d="M115 42v-8h7M195 148v7h-7" />
      </g>
    </svg>
  </div>
</template>
<script setup lang="ts">
defineProps<{ kind: 'diagnostic' | 'plan' | 'communication' | 'narrate' | 'emergency' | 'pre' | 'mid' | 'post' }>()
</script>
<style scoped>
.learning-scene-visual { width:340px; max-width:100%; flex-shrink:0; pointer-events:none; }
svg { display:block; width:100%; height:auto; overflow:visible; stroke-width:1.5; }
.paper { fill:#fff; stroke:#b9d3e8; }
.soft { fill:#edf5fc; stroke:#c6dded; }
.ink { stroke:#39729f; stroke-width:1.8; }
.detail { stroke:#9cbdd6; }
.route { stroke:#729fc2; stroke-width:1.7; stroke-dasharray:4 5; }
.accent { fill:#8db4d3; }
.corner { stroke:#a8c8e0; }
.ground { stroke:#d4e4ef; }
.cloud { stroke:#bed4e5; stroke-width:1.1; opacity:.65; }
</style>
