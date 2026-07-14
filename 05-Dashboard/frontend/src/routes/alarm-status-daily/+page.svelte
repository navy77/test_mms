<script lang="ts">
	import { historyApiUrl } from '$lib/api';
	import { untrack } from 'svelte';
	import HistoryChart from '$lib/components/HistoryChart.svelte';

	let { data } = $props();

	const processesList = $derived(data.processes || []);
	let selectedProcess = $state('');

	$effect(() => {
		selectedProcess = data.initialProcess || '';
	});

	function normalizeAlarmKey(value: unknown) {
		return String(value ?? '')
			.trim()
			.toLowerCase()
			.replace(/\s+/g, '_')
			.replace(/_+$/g, '');
	}

	const colorMap = $derived.by(() => {
		const map: Record<string, string> = {
			'no data': '#EBECEF'
		};

		const activeAlarms = (data.alarms || []).filter((alarm: any) => alarm.process === selectedProcess);
		for (const alarm of activeAlarms) {
			map[normalizeAlarmKey(alarm.status)] = alarm.color;
		}

		return map;
	});

	const statusOrder = $derived([
		...Object.keys(colorMap).filter((status) => status !== 'no data'),
		'no data'
	]);

	const activeDevices = $derived(
		(data.registeredDevices || [])
			.filter((d: any) => d.process === selectedProcess)
			.sort((a: any, b: any) => a.device.localeCompare(b.device, undefined, { numeric: true }))
	);

	let selectedDevices = $state<string[]>([]);
	let selectExpanded = $state(false);

	$effect(() => {
		if (selectedProcess) {
			selectedDevices = activeDevices.map((d: any) => d.device).slice(0, 12);
		}
	});

	const displayedDevices = $derived(
		activeDevices.filter((d: any) => selectedDevices.includes(d.device))
	);

	let dailyRecords = $state<any[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let pollInterval: ReturnType<typeof setInterval> | null = null;

	function normalizeRecords(records: any[]) {
		return records.map((record) => ({
			date: record.date,
			device: record.device,
			utilize: 0,
			data: Array.isArray(record.data)
				? record.data.map((segment: any) => ({
						status: normalizeAlarmKey(segment.alarm ?? segment.status),
						duration: Number(segment.duration ?? 0),
						ratio: Number(segment.ratio ?? 0)
					}))
				: []
		}));
	}

	async function fetchProcessDailyAlarm(processName: string, devices: string[]) {
		if (!processName || devices.length === 0) {
			dailyRecords = [];
			loading = false;
			return;
		}

		loading = dailyRecords.length === 0;
		error = null;

		try {
			const params = new URLSearchParams({ devices: devices.join(',') });
			const res = await fetch(
				historyApiUrl(`/api/v1/alarm/daily/${encodeURIComponent(processName)}?${params}`)
			);
			if (!res.ok) {
				throw new Error(`Failed to fetch daily alarms (${res.status})`);
			}
			const json = await res.json();
			dailyRecords = normalizeRecords(Array.isArray(json) ? json : []);
		} catch (e: any) {
			console.error('Error in fetchProcessDailyAlarm:', e);
			if (dailyRecords.length === 0) {
				error = e.message || 'Failed to load alarm data';
			}
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		if (selectedProcess && selectedDevices.length > 0) {
			const processName = selectedProcess;
			const devices = [...selectedDevices];

			untrack(() => void fetchProcessDailyAlarm(processName, devices));
			if (pollInterval) clearInterval(pollInterval);
			pollInterval = setInterval(() => {
				void fetchProcessDailyAlarm(processName, devices);
			}, 30000);
		} else if (selectedProcess) {
			dailyRecords = [];
			loading = false;
		}

		return () => {
			if (pollInterval) {
				clearInterval(pollInterval);
				pollInterval = null;
			}
		};
	});
</script>

<div class="space-y-5">
	<div class="flex items-center justify-between">
		<h1 class="text-sm font-semibold text-card-foreground">Alarm Daily Ratio</h1>
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

	<div class="flex flex-wrap items-center gap-4 px-4 py-2 border border-border rounded-lg bg-card text-xs">
		<span class="font-medium text-muted-foreground">Legend:</span>
		{#each Object.entries(colorMap) as [alarm, color]}
			{#if alarm !== 'no data'}
				<div class="flex items-center gap-1.5 text-muted-foreground">
					<span class="w-3 h-3 rounded-sm" style="background-color: {color}"></span>
					<span>{alarm}</span>
				</div>
			{/if}
		{/each}
	</div>

	<div class="rounded-lg border border-border bg-card overflow-hidden">
		<button
			type="button"
			onclick={() => (selectExpanded = !selectExpanded)}
			class="w-full flex items-center justify-between px-4 py-3 text-xs font-semibold text-card-foreground hover:bg-muted/30 transition-colors"
		>
			<span>Select Devices to Monitor (Max 12)</span>
			<div class="flex items-center gap-2 text-muted-foreground font-normal">
				<span>{selectedDevices.length} / 12 selected</span>
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
								disabled={!isChecked && selectedDevices.length >= 12}
								onchange={(e) => {
									if (e.currentTarget.checked) {
										if (selectedDevices.length < 12) {
											selectedDevices = [...selectedDevices, dev.device];
										}
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
	{:else if displayedDevices.length === 0}
		<div class="rounded-lg border border-dashed p-12 text-center bg-card">
			<p class="text-sm text-muted-foreground">Please select at least one device above to monitor.</p>
		</div>
	{:else}
		<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
			{#each displayedDevices as dev (dev.device)}
				{@const deviceRecords = dailyRecords.filter((r) => r.device === dev.device)}
				<div class="rounded-lg border border-border bg-card overflow-hidden hover:shadow-md transition-all duration-200">
					<div class="flex items-center justify-between px-3 py-2 border-b border-border/60">
						<div class="flex items-center gap-1.5 min-w-0">
							<span class="h-1.5 w-1.5 rounded-full bg-primary flex-shrink-0 animate-pulse"></span>
							<h3 class="text-xs font-semibold text-foreground truncate">{dev.device}</h3>
						</div>
						<span class="text-[9px] font-medium uppercase text-muted-foreground border border-border/60 rounded px-1 py-0.5 flex-shrink-0">
							{selectedProcess}
						</span>
					</div>
					<div class="px-1 py-1">
						<HistoryChart
							process={selectedProcess}
							device={dev.device}
							{colorMap}
							records={deviceRecords}
							{loading}
							{error}
							{statusOrder}
							showUtilizeLine={false}
						/>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
