<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const data = ref<any>(null)
async function run() { data.value = await api('/refills/run?location_id=1', { method: 'POST' }) }
function statusText(s: string) {
  return s === 'need_fill' ? '待补' : s === 'full' ? '满仓' : s === 'overbooked' ? '超占' : '同品合计已满'
}
onMounted(run)
</script>
<template>
  <h1>补货小票</h1>
  <p class="sub">gap = 容量 − 库存 − 在途 · 同品按货道编号顺序累加上限截断 · 收据纸样式</p>
  <button class="btn" @click="run">生成补货单</button>
  <div style="margin-top:1rem" v-if="data">
    <div class="vf-receipt">
      <h2>*** VendFill 补货单 ***</h2>
      <div class="vf-receipt-line" style="font-weight:700;border-bottom:2px dashed #8a7e64">
        <span>货道 / 商品</span><span>补量</span>
      </div>
      <div class="vf-receipt-line" v-for="l in data.lines" :key="l.lane_id">
        <span>{{ l.slot_no }} {{ l.sku_name }}
          <small :style="l.status === 'cap_full' ? 'color:#b07a1f;font-weight:700' : ''">({{ statusText(l.status) }})</small>
        </span>
        <span>{{ l.fill_qty }} / 缺{{ l.gap }}</span>
      </div>
      <div class="vf-receipt-line" style="font-weight:700;border-top:2px dashed #8a7e64;border-bottom:none">
        <span>合计总件数</span><span>{{ data.total_fill }}</span>
      </div>
      <p style="text-align:center;margin:1rem 0 0;font-size:0.72rem;color:#6a5e48">谢谢使用 · 请核对后装机</p>
    </div>
  </div>
</template>
