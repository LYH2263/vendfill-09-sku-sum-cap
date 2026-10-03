<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api } from '../api'

const props = defineProps<{ locationId: number }>()
const emit = defineEmits<{ changed: [] }>()

interface Cap { id: number; sku_name: string; cap_qty: number }
const rows = ref<Cap[]>([])
const skuOptions = ref<string[]>([])
const newSku = ref('')
const newQty = ref<number | null>(null)
const editQty = ref<Record<string, number>>({})
const err = ref('')
const loading = ref(false)

async function load() {
  const [caps, lanes] = await Promise.all([
    api<Cap[]>(`/sku-caps?location_id=${props.locationId}`),
    api<any[]>(`/lanes?location_id=${props.locationId}`),
  ])
  rows.value = caps
  const registered = new Set(caps.map(c => c.sku_name))
  skuOptions.value = [...new Set(lanes.map(l => l.sku_name))].filter(s => !registered.has(s))
  if (!newSku.value) newSku.value = skuOptions.value[0] ?? ''
  for (const c of caps) editQty.value[c.sku_name] = c.cap_qty
}

async function save(sku: string) {
  err.value = ''
  const qty = editQty.value[sku]
  if (!Number.isInteger(qty) || qty <= 0) {
    err.value = '上限必须为正整数（≤0 已拒绝，登记保持不变）'
    await load()
    return
  }
  loading.value = true
  try {
    await api('/sku-caps', { method: 'PUT', body: JSON.stringify({ location_id: props.locationId, sku_name: sku, cap_qty: qty }) })
    await load()
    emit('changed')
  } catch (e: any) {
    err.value = '保存被拒绝：上限必须为正整数，登记与单据保持改前'
    await load()
  } finally { loading.value = false }
}

async function add() {
  err.value = ''
  const qty = newQty.value
  if (!newSku.value) { err.value = '请选择或填写商品名'; return }
  if (!Number.isInteger(qty) || (qty as number) <= 0) {
    err.value = '上限必须为正整数（≤0 的登记拒绝）'
    newQty.value = null
    return
  }
  loading.value = true
  try {
    await api('/sku-caps', { method: 'PUT', body: JSON.stringify({ location_id: props.locationId, sku_name: newSku.value, cap_qty: qty }) })
    newQty.value = null
    await load()
    emit('changed')
  } catch (e: any) {
    err.value = '登记被拒绝：上限必须为正整数，配置保持改前'
  } finally { loading.value = false }
}

async function remove(sku: string) {
  err.value = ''
  loading.value = true
  try {
    await api(`/sku-caps?location_id=${props.locationId}&sku_name=${encodeURIComponent(sku)}`, { method: 'DELETE' })
    await load()
    emit('changed')
  } finally { loading.value = false }
}

onMounted(load)
watch(() => props.locationId, load)
</script>

<template>
  <div class="card vf-cap-panel">
    <div style="display:flex;align-items:baseline;justify-content:space-between;gap:.5rem;flex-wrap:wrap">
      <strong style="color:var(--vf-led);font-size:.85rem">同品合计补量上限</strong>
      <span class="muted" style="font-size:.68rem">按商品名登记本机合计 · 货道编号顺序累加 · 触顶后续道补 0</span>
    </div>
    <table v-if="rows.length">
      <thead><tr><th>商品名</th><th>合计上限</th><th colspan="2">操作</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>{{ r.sku_name }}</td>
          <td>
            <input class="vf-input" type="number" min="1" step="1"
                   v-model.number="editQty[r.sku_name]" @keyup.enter="save(r.sku_name)" />
          </td>
          <td><button class="btn vf-btn-sm" :disabled="loading" @click="save(r.sku_name)">保存并重算</button></td>
          <td><button class="btn vf-btn-sm vf-btn-ghost" :disabled="loading" @click="remove(r.sku_name)">删除登记</button></td>
        </tr>
      </tbody>
    </table>
    <p v-else class="muted" style="font-size:.72rem;margin:.5rem 0">尚未登记任何商品，未登记商品不受合计约束。</p>
    <div class="vf-cap-add">
      <input class="vf-input" list="vf-sku-suggest" v-model="newSku" placeholder="商品名" />
      <datalist id="vf-sku-suggest">
        <option v-for="s in skuOptions" :key="s" :value="s" />
      </datalist>
      <input class="vf-input" type="number" min="1" step="1" placeholder="正整数上限" v-model.number="newQty" />
      <button class="btn vf-btn-sm" :disabled="loading" @click="add">登记上限</button>
    </div>
    <p v-if="err" class="vf-cap-err">{{ err }}</p>
  </div>
</template>
