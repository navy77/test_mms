<script lang="ts">
	import { dashboardApiUrl } from '$lib/api';
	import { onDestroy } from 'svelte';

	let { data } = $props();

	interface DataRecord {
		status: string;
		payload: Record<string, unknown>;
		timestamp: string;
	}

	const processesList = $derived(data.processes || []);
	let selectedProcess = $state('');

	$effect(() => {
		selectedProcess = data.initialProcess || '';
	});

	let dataMap = $state<Record<string, DataRecord>>({});
	let sse: EventSource | null = null;

	const activeDevices = $derived(
		(data.registeredDevices || [])
			.filter((d: any) => d.process === selectedProcess)
			.sort((a: any, b: any) => a.device.localeCompare(b.device, undefined, { numeric: true }))
	);

	const payloadColumns = $derived(
		(data.columns || [])
			.filter((c: any) => c.process === selectedProcess)
			.map((c: any) => c.column_name)
			.filter((name: string, index: number, list: string[]) => name && list.indexOf(name) === index)
	);

	let selectedDevices = $state<string[]>([]);
	let selectedPayloads = $state<string[]>([]);
	let selectExpanded = $state(false);
	let payloadExpanded = $state(false);
	let currentPage = $state(1);
	const pageSize = 18;

	const displayedDevices = $derived(
		selectedDevices.length > 0
			? activeDevices.filter((d: any) => selectedDevices.includes(d.device))
			: activeDevices.slice((currentPage - 1) * pageSize, currentPage * pageSize)
	);

	const totalPages = $derived(Math.ceil(activeDevices.length / pageSize) || 1);

	const visibleDevicesStr = $derived(displayedDevices.map((d: any) => d.device).join(','));

	$effect(() => {
		if (selectedProcess) {
			selectedDevices = [];
			currentPage = 1;
			dataMap = {};
		}
	});

	$effect(() => {
		if (payloadColumns.length > 0) {
			selectedPayloads = payloadColumns.slice(0, 2);
		} else {
			selectedPayloads = [];
		}
	});

	function formatTime(ts: string) {
		if (!ts) return '—';
		try {
			return new Date(ts).toLocaleString('en-US', {
				hour: '2-digit',
				minute: '2-digit',
				day: '2-digit',
				month: 'short',
				hour12: false
			});
		} catch {
			return '—';
		}
	}

	function formatValue(value: unknown) {
		if (value === null || value === undefined || value === '') return '—';
		if (typeof value === 'number') return Number.isInteger(value) ? value.toString() : value.toFixed(2);
		if (typeof value === 'object') return JSON.stringify(value);
		return String(value);
	}

	function getPayloadValue(payload: Record<string, unknown>, key: string) {
		return payload?.[key];
	}

	function connectSSE(proc: string, devicesStr: string) {
		if (sse) {
			sse.close();
		}
		if (!proc || !devicesStr) return;
		const params = new URLSearchParams({
			process: proc,
			devices: devicesStr
		});

		sse = new EventSource(dashboardApiUrl(`/api/v1/device/realtime/data?${params}`));
		sse.onmessage = (event) => {
			try {
				const list = JSON.parse(event.data);
				const newMap: Record<string, DataRecord> = {};
				for (const item of list) {
					newMap[item.device] = {
						status: item.status || 'no_data',
						payload: item.payload && typeof item.payload === 'object' ? item.payload : {},
						timestamp: item.timestamp || ''
					};
				}
				dataMap = { ...dataMap, ...newMap };
			} catch (err) {
				console.error('Error parsing SSE production data:', err);
			}
		};
	}

	$effect(() => {
		if (selectedProcess && visibleDevicesStr) {
			connectSSE(selectedProcess, visibleDevicesStr);
		} else if (sse) {
			sse.close();
		}
	});

	onDestroy(() => {
		if (sse) sse.close();
	});
</script>

<div class="space-y-6">
	<div class="flex items-center justify-between">
		<h1 class="text-sm font-semibold text-card-foreground">Production Realtime</h1>
		<div class="flex items-center gap-2">
			<span class="text-xs text-muted-foreground font-medium">Process:</span>
			{#if processesList.length > 0}
				<select
					bind:value={selectedProcess}
					class="rounded border border-border bg-background px-3 py-1.5 text-xs text-foreground outline-none focus:border-primary transition-colors cursor-pointer"
				>
					{#each processesList as p}
						<option value={p}>{p}</option>
					{/each}
				</select>
			{:else}
				<span class="text-xs text-muted-foreground italic">Loading processes...</span>
			{/if}
		</div>
	</div>

	<div class="rounded-lg border border-border bg-card overflow-hidden">
		<button
			type="button"
			onclick={() => (payloadExpanded = !payloadExpanded)}
			class="w-full flex items-center justify-between px-4 py-3 text-xs font-semibold text-card-foreground hover:bg-muted/30 transition-colors"
		>
			<span>Select Payload to Display (Max 2)</span>
			<div class="flex items-center gap-2 text-muted-foreground font-normal">
				<span>{selectedPayloads.length} / 2 selected</span>
				<span class="text-[10px]">{payloadExpanded ? '▲' : '▼'}</span>
			</div>
		</button>

		{#if payloadExpanded}
			<div class="p-4 border-t border-border bg-card/50">
				{#if payloadColumns.length === 0}
					<p class="text-xs text-muted-foreground">No payload columns registered for this process.</p>
				{:else}
					<div class="flex flex-wrap gap-2 max-h-40 overflow-y-auto p-1.5 border border-border/50 rounded bg-background/50">
						{#each payloadColumns as column}
							{@const isChecked = selectedPayloads.includes(column)}
							<label
								class="flex items-center gap-1.5 px-2.5 py-1.5 rounded border text-xs cursor-pointer select-none transition-all
								{isChecked ? 'bg-primary/10 border-primary text-primary font-medium' : 'bg-card border-border text-muted-foreground hover:bg-muted'}"
							>
								<input
									type="checkbox"
									checked={isChecked}
									disabled={!isChecked && selectedPayloads.length >= 2}
									onchange={(e) => {
										if (e.currentTarget.checked) {
											if (selectedPayloads.length < 2) selectedPayloads = [...selectedPayloads, column];
										} else {
											selectedPayloads = selectedPayloads.filter((id) => id !== column);
										}
									}}
									class="h-3.5 w-3.5 rounded border-border text-primary focus:ring-primary focus:ring-offset-background"
								/>
								<span>{column}</span>
							</label>
						{/each}
					</div>
				{/if}
			</div>
		{/if}
	</div>

	<div class="rounded-lg border border-border bg-card overflow-hidden">
		<button
			type="button"
			onclick={() => (selectExpanded = !selectExpanded)}
			class="w-full flex items-center justify-between px-4 py-3 text-xs font-semibold text-card-foreground hover:bg-muted/30 transition-colors"
		>
			<span>Select Devices to Monitor (Max 18)</span>
			<div class="flex items-center gap-2 text-muted-foreground font-normal">
				<span>{selectedDevices.length} / 18 selected</span>
				<span class="text-[10px]">{selectExpanded ? '▲' : '▼'}</span>
			</div>
		</button>

		{#if selectExpanded}
			<div class="p-4 border-t border-border bg-card/50">
				<div class="flex flex-wrap gap-2 max-h-40 overflow-y-auto p-1.5 border border-border/50 rounded bg-background/50">
					{#each activeDevices as dev}
						{@const isChecked = selectedDevices.includes(dev.device)}
						<label
							class="flex items-center gap-1.5 px-2.5 py-1.5 rounded border text-xs cursor-pointer select-none transition-all
							{isChecked ? 'bg-primary/10 border-primary text-primary font-medium' : 'bg-card border-border text-muted-foreground hover:bg-muted'}"
						>
							<input
								type="checkbox"
								checked={isChecked}
								disabled={!isChecked && selectedDevices.length >= 18}
								onchange={(e) => {
									if (e.currentTarget.checked) {
										if (selectedDevices.length < 18) selectedDevices = [...selectedDevices, dev.device];
									} else {
										selectedDevices = selectedDevices.filter((id) => id !== dev.device);
									}
								}}
								class="h-3.5 w-3.5 rounded border-border text-primary focus:ring-primary focus:ring-offset-background"
							/>
							<span>{dev.device}</span>
						</label>
					{/each}
				</div>
			</div>
		{/if}
	</div>

	{#if activeDevices.length === 0}
		<div class="rounded-lg border border-dashed p-12 text-center">
			<p class="text-sm text-muted-foreground">No devices registered for this process.</p>
		</div>
	{:else}
		<div class="grid grid-cols-2 gap-3 lg:grid-cols-6">
			{#each displayedDevices as dev}
				{@const record = dataMap[dev.device]}
				{@const payload = record?.payload || {}}
				{@const hasData = record?.status === 'online'}
				<div class="rounded-lg border p-4 transition-all hover:shadow-sm {hasData ? 'border-blue-500/30 bg-blue-500/20' : 'border-border bg-card'}">
					<div class="flex items-center justify-between">
						<div class="flex items-center gap-2 min-w-0">
							<span class="h-2.5 w-2.5 rounded-full {hasData ? 'animate-pulse bg-emerald-500' : 'bg-muted-foreground/50'}"></span>
							<p class="text-md font-semibold text-foreground truncate">{dev.device}</p>
						</div>
						<span class="rounded-full border border-border px-2 py-0.5 text-[10px] font-medium uppercase text-muted-foreground">
							{dev.process}
						</span>
					</div>

					<div class="mt-3 grid gap-2">
						{#if selectedPayloads.length === 0}
							<div class="rounded border border-dashed border-border px-3 py-3 text-center text-xs text-muted-foreground">
								No payload selected
							</div>
						{:else}
							{#each selectedPayloads as key}
								<div class="rounded border border-border/70 bg-background/50 px-3 py-2">
									<p class="text-[10px] uppercase tracking-normal text-muted-foreground truncate">{key}</p>
									<p class="mt-0.5 text-lg font-semibold text-foreground truncate" title={formatValue(getPayloadValue(payload, key))}>
										{formatValue(getPayloadValue(payload, key))}
									</p>
								</div>
							{/each}
						{/if}
					</div>

					<p class="mt-3 text-[12px] text-muted-foreground whitespace-nowrap">
						Last update: {formatTime(record?.timestamp || '')}
					</p>
				</div>
			{/each}
		</div>
	{/if}

	{#if selectedDevices.length === 0}
		<div class="flex items-center justify-between border-t border-border px-4 py-2.5 bg-muted/18 rounded-lg">
			<p class="text-xs text-muted-foreground">
				Showing {(currentPage - 1) * pageSize + 1} to {Math.min(currentPage * pageSize, activeDevices.length)} of {activeDevices.length} rows
			</p>
			<div class="flex items-center gap-1.5">
				<button
					onclick={() => (currentPage = Math.max(1, currentPage - 1))}
					disabled={currentPage === 1}
					class="rounded border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted disabled:opacity-50"
				>
					Previous
				</button>
				<span class="text-xs text-muted-foreground px-2">Page {currentPage} of {totalPages}</span>
				<button
					onclick={() => (currentPage = Math.min(totalPages, currentPage + 1))}
					disabled={currentPage === totalPages}
					class="rounded border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted disabled:opacity-50"
				>
					Next
				</button>
			</div>
		</div>
	{/if}
</div>
