<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { matchResultLabel } from '../lib/labels';
  import type { ColorMatchTicket, MatchResult, Mill } from '../lib/types';

  const HEX_RE = /^#?[0-9a-fA-F]{6}$/;
  const PASS_MAX_DELTA_E = 2;

  let rows: ColorMatchTicket[] = [];
  let mills: Mill[] = [];
  let error = '';
  let editingId: number | null = null;
  let resultFilter: '' | MatchResult = '';

  let form = {
    ticketNo: '',
    targetHex: '#C0392B',
    sampleHex: '#C13A2C',
    deltaE: '1.0',
    millId: '',
  };

  $: targetValid = HEX_RE.test(form.targetHex.trim());
  $: sampleValid = HEX_RE.test(form.sampleHex.trim());
  $: deltaNum = Number(form.deltaE);
  $: deltaValid = form.deltaE.trim() !== '' && Number.isFinite(deltaNum) && deltaNum >= 0;
  // 表单实时判定:ΔE ≤ 2 → pass,否则 fail
  let formResult: MatchResult | null = null;
  $: formResult = deltaValid ? (deltaNum <= PASS_MAX_DELTA_E ? 'pass' : 'fail') : null;

  async function load() {
    error = '';
    try {
      const query = resultFilter ? `?result=${resultFilter}` : '';
      [rows, mills] = await Promise.all([
        api<ColorMatchTicket[]>(`/color-match-tickets${query}`),
        api<Mill[]>('/mills'),
      ]);
    } catch (e) {
      error = e instanceof Error ? e.message : '加载失败';
    }
  }

  onMount(load);

  function setFilter(value: '' | MatchResult) {
    resultFilter = value;
    load();
  }

  function millLabel(id: number | null): string {
    if (id == null) return '—';
    const m = mills.find((x) => x.id === id);
    return m ? `${m.millCode} (#${m.id})` : `#${id}`;
  }

  function reset() {
    form = { ticketNo: '', targetHex: '#C0392B', sampleHex: '#C13A2C', deltaE: '1.0', millId: '' };
    editingId = null;
  }

  function edit(row: ColorMatchTicket) {
    editingId = row.id;
    form = {
      ticketNo: row.ticketNo,
      targetHex: row.targetHex,
      sampleHex: row.sampleHex,
      deltaE: String(row.deltaE),
      millId: row.millId != null ? String(row.millId) : '',
    };
  }

  async function save() {
    error = '';
    if (!form.ticketNo.trim()) {
      error = '比对单号不能为空';
      return;
    }
    if (!targetValid) {
      error = '目标色须为 #RRGGBB 六位十六进制格式';
      return;
    }
    if (!sampleValid) {
      error = '小样色须为 #RRGGBB 六位十六进制格式';
      return;
    }
    if (!deltaValid) {
      error = 'ΔE 必须为不小于 0 的数字';
      return;
    }
    // 前端一致性拦截:判定只能由 ΔE 推出,不允许提交不一致组合
    const result: MatchResult = deltaNum <= PASS_MAX_DELTA_E ? 'pass' : 'fail';
    if (result !== formResult) {
      error = '判定结果与 ΔE 不一致';
      return;
    }
    const payload = {
      ticketNo: form.ticketNo.trim(),
      targetHex: form.targetHex.trim(),
      sampleHex: form.sampleHex.trim(),
      deltaE: deltaNum,
      result,
      millId: form.millId === '' ? null : Number(form.millId),
    };
    try {
      if (editingId) {
        await api(`/color-match-tickets/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
      } else {
        await api('/color-match-tickets', { method: 'POST', body: JSON.stringify(payload) });
      }
      reset();
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : '保存失败';
    }
  }

  async function remove(id: number) {
    if (!confirm('确认删除该专色比对单？')) return;
    try {
      await api(`/color-match-tickets/${id}`, { method: 'DELETE' });
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : '删除失败';
    }
  }
</script>

<header class="page-head">
  <h1>专色比对</h1>
  <p>专色小样与目标色比对:ΔE ≤ 2 判合格,&gt; 2 判不合格(前后端同时校验)</p>
</header>

{#if error}
  <div class="err">{error}</div>
{/if}

<section class="panel">
  <h2>{editingId ? '编辑比对单' : '新增比对单'}</h2>
  <div class="fields">
    <div class="field"><label>比对单号<input placeholder="如 SC-2026-0004" bind:value={form.ticketNo} /></label></div>
    <div class="field">
      <label>研磨机(可选)
        <select bind:value={form.millId}>
          <option value="">(不关联)</option>
          {#each mills as m}
            <option value={String(m.id)}>{m.millCode}</option>
          {/each}
        </select>
      </label>
    </div>
    <div class="field">
      <label>目标色 Hex<input placeholder="#RRGGBB" bind:value={form.targetHex} /></label>
      {#if targetValid}
        <div class="hint"><span class="swatch" style="background:{form.targetHex}"></span>{form.targetHex}</div>
      {/if}
    </div>
    <div class="field">
      <label>小样色 Hex<input placeholder="#RRGGBB" bind:value={form.sampleHex} /></label>
      {#if sampleValid}
        <div class="hint"><span class="swatch" style="background:{form.sampleHex}"></span>{form.sampleHex}</div>
      {/if}
    </div>
    <div class="field">
      <label>ΔE 色差<input type="number" step="0.0001" min="0" bind:value={form.deltaE} /></label>
      {#if formResult}
        <div class="hint">判定:<span class="badge {formResult}">{matchResultLabel[formResult]}</span></div>
      {/if}
    </div>
  </div>
  <div class="actions">
    <button class="btn-primary" on:click={save}>{editingId ? '保存' : '创建'}</button>
    {#if editingId}
      <button class="btn-ghost" on:click={reset}>取消</button>
    {/if}
  </div>
</section>

<section class="panel">
  <div class="filter-bar">
    <button class:active={resultFilter === ''} on:click={() => setFilter('')}>全部</button>
    <button class:active={resultFilter === 'pass'} on:click={() => setFilter('pass')}>合格</button>
    <button class:active={resultFilter === 'fail'} on:click={() => setFilter('fail')}>不合格</button>
  </div>
  <table class="data-table">
    <thead>
      <tr>
        <th>ID</th>
        <th>单号</th>
        <th>目标色</th>
        <th>小样色</th>
        <th>ΔE</th>
        <th>判定</th>
        <th>研磨机</th>
        <th>创建时间</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr>
          <td>{row.id}</td>
          <td>{row.ticketNo}</td>
          <td><span class="swatch" style="background:{row.targetHex}"></span>{row.targetHex}</td>
          <td><span class="swatch" style="background:{row.sampleHex}"></span>{row.sampleHex}</td>
          <td>{row.deltaE}</td>
          <td><span class="badge {row.result}">{matchResultLabel[row.result]}</span></td>
          <td>{millLabel(row.millId)}</td>
          <td>{row.createdAt}</td>
          <td class="ops">
            <button class="link-btn" on:click={() => edit(row)}>编辑</button>
            <button class="link-btn danger" on:click={() => remove(row.id)}>删除</button>
          </td>
        </tr>
      {:else}
        <tr><td colspan="9">暂无数据</td></tr>
      {/each}
    </tbody>
  </table>
</section>

<style>
  .hint {
    margin-top: 0.3rem;
    font-size: 0.8rem;
    color: var(--steel);
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .filter-bar {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.8rem;
  }

  .filter-bar button {
    border: 1px solid var(--line);
    background: transparent;
    color: var(--steel);
    padding: 0.35rem 0.9rem;
    cursor: pointer;
    border-radius: 2px;
  }

  .filter-bar button.active {
    border-color: var(--vermillion-700);
    color: white;
    background: rgba(192, 57, 43, 0.18);
  }
</style>
