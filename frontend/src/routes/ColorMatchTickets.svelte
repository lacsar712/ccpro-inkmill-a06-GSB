<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { colorMatchResultLabel } from '../lib/labels';
  import type { ColorMatchResult, ColorMatchTicket, Mill } from '../lib/types';

  const HEX_RE = /^#[0-9a-fA-F]{6}$/;
  const PASS_THRESHOLD = 2;

  let rows: ColorMatchTicket[] = [];
  let mills: Mill[] = [];
  let error = '';
  let editingId: number | null = null;
  let filter: '' | ColorMatchResult = '';

  let form = {
    ticketNo: '',
    targetHex: '#C0392B',
    sampleHex: '#C13B2E',
    deltaE: '1.00',
    millId: '',
  };

  $: deltaNum = Number(form.deltaE);
  $: deltaValid = form.deltaE.trim() !== '' && Number.isFinite(deltaNum) && deltaNum >= 0;
  let computedResult: ColorMatchResult;
  $: computedResult = deltaValid && deltaNum <= PASS_THRESHOLD ? 'pass' : 'fail';

  async function load() {
    error = '';
    try {
      const query = filter ? `?result=${filter}` : '';
      [rows, mills] = await Promise.all([
        api<ColorMatchTicket[]>(`/color-match-tickets${query}`),
        api<Mill[]>('/mills'),
      ]);
    } catch (e) {
      error = e instanceof Error ? e.message : '加载失败';
    }
  }

  onMount(load);

  function setFilter(value: '' | ColorMatchResult) {
    filter = value;
    load();
  }

  function millLabel(id: number | null): string {
    if (id === null) return '—';
    const m = mills.find((x) => x.id === id);
    return m ? `${m.millCode} (#${m.id})` : `#${id}`;
  }

  function reset() {
    form = {
      ticketNo: '',
      targetHex: '#C0392B',
      sampleHex: '#C13B2E',
      deltaE: '1.00',
      millId: '',
    };
    editingId = null;
  }

  function edit(row: ColorMatchTicket) {
    editingId = row.id;
    form = {
      ticketNo: row.ticketNo,
      targetHex: row.targetHex,
      sampleHex: row.sampleHex,
      deltaE: String(row.deltaE),
      millId: row.millId !== null ? String(row.millId) : '',
    };
  }

  function validateForm(): string {
    if (!form.ticketNo.trim()) return '比对单号不能为空';
    if (!HEX_RE.test(form.targetHex.trim())) return '目标色值格式应为 #RRGGBB';
    if (!HEX_RE.test(form.sampleHex.trim())) return '小样色值格式应为 #RRGGBB';
    if (!deltaValid) return 'ΔE 必须为 ≥ 0 的数值';
    return '';
  }

  async function save() {
    error = validateForm();
    if (error) return;

    const payload = {
      ticketNo: form.ticketNo.trim(),
      targetHex: form.targetHex.trim(),
      sampleHex: form.sampleHex.trim(),
      deltaE: deltaNum,
      result: computedResult,
      millId: form.millId ? Number(form.millId) : null,
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
  <h1>专色小样比对</h1>
  <p>ΔE ≤ 2 判合格(pass)，ΔE &gt; 2 判不合格(fail)，结果由 ΔE 自动判定</p>
</header>

{#if error}
  <div class="err">{error}</div>
{/if}

<section class="panel">
  <h2>{editingId ? '编辑比对单' : '新增比对单'}</h2>
  <div class="fields">
    <div class="field"><label>比对单号<input bind:value={form.ticketNo} placeholder="CM-2026-0001" /></label></div>
    <div class="field">
      <label>目标色值
        <span class="hex-input">
          <input type="color" bind:value={form.targetHex} />
          <input type="text" bind:value={form.targetHex} placeholder="#RRGGBB" />
        </span>
      </label>
    </div>
    <div class="field">
      <label>小样色值
        <span class="hex-input">
          <input type="color" bind:value={form.sampleHex} />
          <input type="text" bind:value={form.sampleHex} placeholder="#RRGGBB" />
        </span>
      </label>
    </div>
    <div class="field"><label>ΔE<input type="number" min="0" step="0.01" bind:value={form.deltaE} /></label></div>
    <div class="field">
      <label>关联研磨机（可选）
        <select bind:value={form.millId}>
          <option value="">不关联</option>
          {#each mills as m}
            <option value={String(m.id)}>{m.millCode}</option>
          {/each}
        </select>
      </label>
    </div>
    <div class="field">
      <span class="field-label">判定结果</span>
      <div class="result-preview">
        {#if deltaValid}
          <span class="badge {computedResult}">{colorMatchResultLabel[computedResult]}</span>
          <span class="muted">ΔE {deltaNum} {computedResult === 'pass' ? '≤' : '>'} {PASS_THRESHOLD}</span>
        {:else}
          <span class="muted">输入有效 ΔE 后自动判定</span>
        {/if}
      </div>
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
  <div class="filters">
    <button class:active={filter === ''} on:click={() => setFilter('')}>全部</button>
    <button class:active={filter === 'pass'} on:click={() => setFilter('pass')}>合格</button>
    <button class:active={filter === 'fail'} on:click={() => setFilter('fail')}>不合格</button>
  </div>
  <table class="data-table">
    <thead>
      <tr>
        <th>ID</th>
        <th>单号</th>
        <th>目标色</th>
        <th>小样色</th>
        <th>ΔE</th>
        <th>结果</th>
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
          <td><span class="badge {row.result}">{colorMatchResultLabel[row.result]}</span></td>
          <td>{millLabel(row.millId)}</td>
          <td>{row.createdAt || '—'}</td>
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
