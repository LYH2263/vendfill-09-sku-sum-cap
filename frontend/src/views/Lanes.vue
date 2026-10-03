<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import SkuCapEditor from '../components/SkuCapEditor.vue'
const LOCATION_ID = 1
const rows = ref<any[]>([])
const refill = ref<any>(null)

async function loadLanes() { rows.value = await api(`/lanes?location_id=${LOCATION_ID}`) }
async function runRefill() {
  try { refill.value = await api(`/refills/run?location_id=${LOCATION_ID}`, { method: 'POST' }) } catch { /* */ }
}
async function onCapChanged() {
  // Config changed: regenerate against the new aggregate and refresh the grid.
  await Promise.all([loadLanes(), runRefill()])
}
onMounted(async () => { await Promise.all([loadLanes(), runRefill()]) })
</script>
<template>
  <h1>货道格子</h1>
  <p class="sub">机面货道网格 · 格内库存条 · 右侧补货小票 · 同品合计触顶置 0</p>
  <div class="vf-machine-layout">
    <div>
      <div class="vf-slot-grid">
        <div v-for="r in rows" :key="r.id" class="vf-slot" :class="{ 'vf-slot-cap': r.status === 'cap_full' }">
          <div class="vf-slot-no">{{ r.slot_no }}</div>
          <div class="vf-slot-sku">{{ r.sku_name }}</div>
          <div class="vf-slot-bar">
            <div
              class="vf-slot-fill"
              :class="{ 'vf-need': r.gap > 0 && r.status !== 'cap_full' }"
              :style="{ width: Math.min(r.fill_pct, 100) + '%' }"
            />
          </div>
          <div class="vf-slot-meta">{{ r.stock }}/{{ r.capacity }} · 缺 {{ r.gap }} · 补 {{ r.fill_qty }}</div>
          <span v-if="r.status === 'cap_full'" class="vf-cap-tag">同品合计已满</span>
        </div>
      </div>
      <SkuCapEditor :location-id="LOCATION_ID" @changed="onCapChanged" />
    </div>
    <aside class="vf-receipt" v-if="refill">
      <h2>*** 补货建议单 ***</h2>
      <div class="vf-receipt-line" v-for="l in refill.lines" :key="l.lane_id">
        <span>{{ l.slot_no }} {{ l.sku_name }}</span>
        <span>x{{ l.fill_qty }}
          <small v-if="l.status === 'cap_full'" style="color:#b07a1f">（同品合计已满）</small>
        </span>
      </div>
      <p class="muted" style="margin:0.75rem 0 0;font-size:0.72rem;color:#6a5e48;text-align:center">
        合计 {{ refill.total_fill }} 件 — 机面打印预览 —
      </p>
    </aside>
  </div>
</template>
