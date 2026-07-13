<script lang="ts">
	import { onDestroy } from 'svelte';

	let { data } = $props();

	const processesList = $derived(data.processes || []);
	let selectedProcess = $state('');

	$effect(() => {
		selectedProcess = data.initialProcess || '';
	});

	let alarmMap = $state<Record<string, { status: string; timestamp: string }>>({});
	let sse: EventSource | null = null;

	const defaultColors: Record<string, string> = {
		alarm: '#ef4444',   // red-500
		normal: '#22c55e'   // green-500
	};

	const statusLabels: Record<string, string> = {
		alarm: 'Active Alarms',
		normal: 'Normal'
	};

	const colorMap = $derived.by(() => {
		const map: Record<string, string> = { ...defaultColors };
		const activeAlarms = (data.alarms || []).filter((a: any) => a.process === selectedProcess);
		for (const a of activeAlarms) {
			map[a.status] = a.color;
		}
		return map;
	});

	function getStatusStyle(rawStat: string, resolvedStat?: string) {
		const color = colorMap[rawStat] || (resolvedStat ? colorMap[resolvedStat] : null) || colorMap['normal'] || '#22c55e';
		return `--status-color: ${color}; border-color: color-mix(in srgb, ${color} 30%, transparent); background-color: color-mix(in srgb, ${color} 10%, transparent);`;
	}

	const activeDevices = $derived(
		(data.registeredDevices || [])
			.filter((d: any) => d.process === selectedProcess)
			.sort((a: any, b: any) => a.device.localeCompare(b.device, undefined, { numeric: true }))
	);

	function resolveAlarmStatus(rawStat: string | undefined) {
		if (!rawStat || rawStat === 'normal') return 'normal';
		if (rawStat.endsWith('_')) {
			return 'normal';
		}
		if (rawStat.startsWith('alarm')) {
			return 'alarm';
		}
		return 'normal';
	}

	const summary = $derived.by(() => {
		let activeCount = 0;
		for (const d of activeDevices) {
			const record = alarmMap[d.device];
			const rawStat = record ? record.status : 'normal';
			const stat = resolveAlarmStatus(rawStat);
			if (stat === 'alarm') {
				activeCount++;
			}
		}
		return {
			alarm: activeCount,
			normal: Math.max(0, activeDevices.length - activeCount)
		};
	});

	let selectedDevices = $state<string[]>([]);
	let selectExpanded = $state(false);
	let currentPage = $state(1);
	const pageSize = 18;

	const displayedDevices = $derived(
		selectedDevices.length > 0
			? activeDevices.filter((d: any) => selectedDevices.includes(d.device))
			: activeDevices.slice((currentPage - 1) * pageSize, currentPage * pageSize)
	);

	const totalPages = $derived(Math.ceil(activeDevices.length / pageSize) || 1);

	const visibleDevicesStr = $derived(
		displayedDevices.map((d: any) => d.device).join(',')
	);

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

	function connectSSE(proc: string, devicesStr: string) {
		if (sse) {
			sse.close();
		}
		if (!proc || !devicesStr) return;
		const host = window.location.hostname;
		sse = new EventSource(`http://${host}:8001/api/v1/device/realtime/alarm-status?process=${proc}&devices=${devicesStr}`);
		sse.onmessage = (event) => {
			try {
				const list = JSON.parse(event.data);
				const newMap: Record<string, { status: string; timestamp: string }> = {};
				for (const item of list) {
					newMap[item.device] = {
						status: item.status || 'normal',
						timestamp: item.timestamp || ''
					};
				}
				alarmMap = { ...alarmMap, ...newMap };
			} catch (err) {
				console.error('Error parsing SSE alarm:', err);
			}
		};
	}

	$effect(() => {
		if (selectedProcess && visibleDevicesStr) {
			connectSSE(selectedProcess, visibleDevicesStr);
		} else {
			if (sse) sse.close();
		}
	});

	onDestroy(() => {
		if (sse) sse.close();
	});

	$effect(() => {
		selectedProcess;
		selectedDevices = [];
		currentPage = 1;
		alarmMap = {};
	});
</script>

<div class="space-y-6">
	<!-- Header with Dropdown -->
	<div class="flex items-center justify-between">
		<h1 class="text-sm font-semibold text-card-foreground">Alarm Status Overview</h1>
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

	<!-- Summary Row -->
	<div class="grid grid-cols-2 gap-3">
		{#each Object.entries(summary) as [status, count]}
			{@const label = statusLabels[status as keyof typeof statusLabels] || status}
			<div class="rounded-lg border p-4 text-center transition-all duration-200" style={getStatusStyle(status)}>
				<div class="flex items-center justify-center gap-1.5">
					<span class="h-2 w-2 rounded-full {status === 'alarm' && count > 0 ? 'animate-pulse' : ''}" style="background-color: var(--status-color);"></span>
					<span class="text-xs text-muted-foreground">{label}</span>
				</div>
				<p class="mt-1 text-3xl font-semibold" style="color: var(--status-color);">{count}</p>
			</div>
		{/each}
	</div>

	<!-- Select Machine (Collapsible) -->
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
										if (selectedDevices.length < 18) {
											selectedDevices = [...selectedDevices, dev.device];
										}
									} else {
										selectedDevices = selectedDevices.filter(id => id !== dev.device);
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

	<!-- Machine Grid -->
	<div class="grid grid-cols-2 gap-3 lg:grid-cols-6">
		{#each displayedDevices as dev}
			{@const record = alarmMap[dev.device]}
			{@const rawStat = record ? record.status : 'normal'}
			{@const stat = resolveAlarmStatus(rawStat)}
			{@const timestamp = record ? record.timestamp : ''}
			{@const label = stat === 'alarm' ? rawStat : 'Normal'}
			<div class="rounded-lg border p-4 transition-all hover:shadow-sm" style={getStatusStyle(rawStat, stat)}>
				<!-- Header -->
				<div class="flex items-center justify-between">
					<div class="flex items-center gap-2">
						<span class="h-2.5 w-2.5 rounded-full {stat === 'alarm' ? 'animate-pulse' : ''}" style="background-color: var(--status-color);"></span>
						<p class="text-md font-semibold text-foreground">{dev.device}</p>
					</div>
					<span class="rounded-full border border-border px-2 py-0.5 text-[10px] font-medium uppercase text-muted-foreground">
						{dev.process}
					</span>
				</div>

				<!-- Status Badge -->
				<p class="mt-1 text-md font-medium capitalize" style="color: var(--status-color);">
					{label}
				</p>

				<!-- Timestamp -->
				<p class="mt-2 text-[15px] text-muted-foreground whitespace-nowrap">
					Last Update: {formatTime(timestamp)}
				</p>
			</div>
		{/each}
	</div>

	<!-- Pagination Footer (Only shown when not filtering by specific selections) -->
	{#if selectedDevices.length === 0}
		<div class="flex items-center justify-between border-t border-border px-4 py-2.5 bg-muted/20 rounded-lg">
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
