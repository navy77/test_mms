<script lang="ts">
	import { dashboardApiUrl } from '$lib/api';
	import { onDestroy } from 'svelte';
	import {
		Activity,
		AlertTriangle,
		BarChart3,
		Bell,
		CheckCircle2,
		Cpu,
		Database,
		Factory,
		HardDrive,
		Radio,
		Server
	} from '@lucide/svelte';

	let { data } = $props();

	interface DataRecord {
		device: string;
		status: string;
		payload: Record<string, unknown>;
		timestamp: string;
	}

	const processes = $derived(data.processes || []);
	const registeredDevices = $derived(data.registeredDevices || []);
	const deviceCounts = $derived(data.deviceCounts || []);
	const health = $derived(data.health || { status: 'offline' });

	const totalDevices = $derived(
		deviceCounts.reduce((sum: number, item: any) => sum + Number(item.total || 0), 0)
	);
	const onlineDevices = $derived(
		deviceCounts.reduce((sum: number, item: any) => sum + Number(item.online || 0), 0)
	);
	const offlineDevices = $derived(
		deviceCounts.reduce((sum: number, item: any) => sum + Number(item.offline || 0), 0)
	);
	const communicationFail = $derived(
		deviceCounts.reduce((sum: number, item: any) => sum + Number(item.communication_fail || 0), 0)
	);
	const onlineRate = $derived(totalDevices > 0 ? Math.round((onlineDevices / totalDevices) * 100) : 0);
	const registeredProcesses = $derived(processes.length);
	const registeredColumns = $derived((data.columns || []).length);
	const configuredAlarms = $derived((data.alarms || []).length);
	const configuredStatuses = $derived((data.statuses || []).length);

	let selectedProcess = $state('');
	let recentData = $state<DataRecord[]>([]);
	let dataSse: EventSource | null = null;

	$effect(() => {
		selectedProcess = data.initialProcess || '';
	});

	const selectedDevices = $derived(
		registeredDevices
			.filter((device: any) => device.process === selectedProcess)
			.sort((a: any, b: any) => a.device.localeCompare(b.device, undefined, { numeric: true }))
			.slice(0, 8)
	);

	const visibleDevicesStr = $derived(selectedDevices.map((device: any) => device.device).join(','));

	const selectedPayloadColumns = $derived(
		(data.columns || [])
			.filter((column: any) => column.process === selectedProcess)
			.map((column: any) => column.column_name)
			.filter((name: string, index: number, list: string[]) => name && list.indexOf(name) === index)
			.slice(0, 3)
	);

	const processRows = $derived(
		deviceCounts.map((item: any) => ({
			...item,
			onlineRate: item.total > 0 ? Math.round((item.online / item.total) * 100) : 0
		}))
	);

	const kpiCards = $derived([
		{
			label: 'Online Devices',
			value: `${onlineDevices} / ${totalDevices}`,
			helper: `${onlineRate}% online`,
			icon: HardDrive,
			color: '#22c55e'
		},
		{
			label: 'Communication Fail',
			value: String(communicationFail),
			helper: `${offlineDevices} offline`,
			icon: AlertTriangle,
			color: '#f59e0b'
		},
		{
			label: 'Processes',
			value: String(registeredProcesses),
			helper: `${registeredColumns} columns`,
			icon: Factory,
			color: '#3b82f6'
		},
		{
			label: 'Alarm Rules',
			value: String(configuredAlarms),
			helper: `${configuredStatuses} machine states`,
			icon: Bell,
			color: '#ef4444'
		}
	]);

	const healthItems = $derived([
		{ label: 'Dashboard API', status: health.status === 'healthy' ? 'online' : 'offline', icon: Server },
		{ label: 'PostgreSQL', status: health.postgres === 'connected' ? 'online' : 'offline', icon: Database },
		{ label: 'Realtime Redis', status: health.status === 'healthy' ? 'online' : 'unknown', icon: Radio },
		{ label: 'ClickHouse', status: health.status === 'healthy' ? 'online' : 'unknown', icon: Activity }
	]);

	function connectDataStream(process: string, devices: string) {
		if (dataSse) {
			dataSse.close();
			dataSse = null;
		}
		if (!process || !devices) return;
		const params = new URLSearchParams({ process, devices });
		dataSse = new EventSource(dashboardApiUrl(`/api/v1/device/realtime/data?${params}`));
		dataSse.onmessage = (event) => {
			try {
				const list = JSON.parse(event.data);
				recentData = Array.isArray(list)
					? list.map((item: any) => ({
							device: item.device,
							status: item.status || 'no_data',
							payload: item.payload && typeof item.payload === 'object' ? item.payload : {},
							timestamp: item.timestamp || ''
						}))
					: [];
			} catch (err) {
				console.error('Error parsing home realtime data:', err);
			}
		};
	}

	$effect(() => {
		if (selectedProcess && visibleDevicesStr) {
			connectDataStream(selectedProcess, visibleDevicesStr);
		} else if (dataSse) {
			dataSse.close();
			dataSse = null;
		}
	});

	onDestroy(() => {
		if (dataSse) dataSse.close();
	});

	function formatTime(ts: string) {
		if (!ts) return '-';
		try {
			return new Date(ts).toLocaleString('en-US', {
				hour: '2-digit',
				minute: '2-digit',
				day: '2-digit',
				month: 'short',
				hour12: false
			});
		} catch {
			return '-';
		}
	}

	function formatValue(value: unknown) {
		if (value === null || value === undefined || value === '') return '-';
		if (typeof value === 'number') return Number.isInteger(value) ? value.toString() : value.toFixed(2);
		if (typeof value === 'object') return JSON.stringify(value);
		return String(value);
	}
</script>

<div class="space-y-5">
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-sm font-semibold text-card-foreground">Operations Overview</h1>
			<p class="mt-1 text-xs text-muted-foreground">Realtime health, device availability, and latest production signals.</p>
		</div>
		<div class="flex items-center gap-2">
			<span class="text-xs font-medium text-muted-foreground">Process:</span>
			{#if processes.length > 0}
				<select
					bind:value={selectedProcess}
					class="rounded border border-border bg-background px-3 py-1.5 text-xs text-foreground outline-none focus:border-primary transition-colors cursor-pointer"
				>
					{#each processes as process}
						<option value={process}>{process}</option>
					{/each}
				</select>
			{:else}
				<span class="text-xs italic text-muted-foreground">No process registered</span>
			{/if}
		</div>
	</div>

	<div class="grid grid-cols-2 gap-3 xl:grid-cols-4">
		{#each kpiCards as card}
			<div class="rounded-lg border border-border bg-card p-4">
				<div class="flex items-center justify-between">
					<p class="text-xs font-medium text-muted-foreground">{card.label}</p>
					<span class="rounded-md p-1.5" style="background-color: color-mix(in srgb, {card.color} 12%, transparent);">
						<card.icon class="h-3.5 w-3.5" style="color: {card.color}" />
					</span>
				</div>
				<p class="mt-2 text-2xl font-semibold text-card-foreground">{card.value}</p>
				<p class="mt-1 text-xs text-muted-foreground">{card.helper}</p>
			</div>
		{/each}
	</div>

	<div class="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
		<div class="rounded-lg border border-border bg-card p-4">
			<div class="mb-4 flex items-center justify-between">
				<div class="flex items-center gap-2">
					<BarChart3 class="h-4 w-4 text-primary" />
					<h2 class="text-sm font-semibold text-card-foreground">Device Availability by Process</h2>
				</div>
				<span class="text-xs text-muted-foreground">{totalDevices} registered devices</span>
			</div>
			<div class="space-y-3">
				{#each processRows as row}
					<div class="rounded-md border border-border bg-background px-3 py-3">
						<div class="mb-2 flex items-center justify-between gap-3">
							<div class="min-w-0">
								<p class="truncate text-xs font-semibold text-foreground">{row.process}</p>
								<p class="text-[11px] text-muted-foreground">
									{row.online} online, {row.offline} offline, {row.communication_fail} communication fail
								</p>
							</div>
							<span class="text-xs font-semibold text-foreground">{row.onlineRate}%</span>
						</div>
						<div class="h-2 overflow-hidden rounded-full bg-muted">
							<div class="h-full rounded-full bg-green-500" style="width: {row.onlineRate}%"></div>
						</div>
					</div>
				{:else}
					<p class="rounded-md border border-dashed border-border px-3 py-8 text-center text-xs text-muted-foreground">
						No process data available.
					</p>
				{/each}
			</div>
		</div>

		<div class="rounded-lg border border-border bg-card p-4">
			<div class="mb-4 flex items-center gap-2">
				<CheckCircle2 class="h-4 w-4 text-green-500" />
				<h2 class="text-sm font-semibold text-card-foreground">System Health</h2>
			</div>
			<div class="space-y-2">
				{#each healthItems as item}
					<div class="flex items-center gap-3 rounded-md border border-border bg-background px-3 py-2.5">
						<item.icon class="h-4 w-4 text-muted-foreground" />
						<div class="min-w-0 flex-1">
							<p class="text-xs font-medium text-foreground">{item.label}</p>
						</div>
						<span
							class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase
							{item.status === 'online'
								? 'bg-green-500/10 text-green-600 dark:text-green-400'
								: item.status === 'unknown'
									? 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400'
									: 'bg-red-500/10 text-red-600 dark:text-red-400'}"
						>
							<span
								class="h-1.5 w-1.5 rounded-full {item.status === 'online'
									? 'bg-green-500'
									: item.status === 'unknown'
										? 'bg-yellow-500'
										: 'bg-red-500'}"
							></span>
							{item.status}
						</span>
					</div>
				{/each}
			</div>
		</div>
	</div>

	<div class="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
		<div class="rounded-lg border border-border bg-card p-4">
			<div class="mb-4 flex items-center gap-2">
				<Cpu class="h-4 w-4 text-blue-500" />
				<h2 class="text-sm font-semibold text-card-foreground">Configuration Snapshot</h2>
			</div>
			<div class="grid grid-cols-2 gap-3">
				<div class="rounded-md border border-border bg-background px-3 py-3">
					<p class="text-[11px] text-muted-foreground">Devices</p>
					<p class="mt-1 text-xl font-semibold text-foreground">{registeredDevices.length}</p>
				</div>
				<div class="rounded-md border border-border bg-background px-3 py-3">
					<p class="text-[11px] text-muted-foreground">Columns</p>
					<p class="mt-1 text-xl font-semibold text-foreground">{registeredColumns}</p>
				</div>
				<div class="rounded-md border border-border bg-background px-3 py-3">
					<p class="text-[11px] text-muted-foreground">Statuses</p>
					<p class="mt-1 text-xl font-semibold text-foreground">{configuredStatuses}</p>
				</div>
				<div class="rounded-md border border-border bg-background px-3 py-3">
					<p class="text-[11px] text-muted-foreground">Alarms</p>
					<p class="mt-1 text-xl font-semibold text-foreground">{configuredAlarms}</p>
				</div>
			</div>
		</div>

		<div class="rounded-lg border border-border bg-card p-4">
			<div class="mb-4 flex items-center justify-between gap-3">
				<div class="flex items-center gap-2">
					<Activity class="h-4 w-4 text-primary" />
					<h2 class="text-sm font-semibold text-card-foreground">Latest Production Signals</h2>
				</div>
				<span class="text-xs text-muted-foreground">{selectedProcess || 'No process'}</span>
			</div>
			<div class="overflow-hidden rounded-md border border-border">
				<table class="w-full text-xs">
					<thead class="border-b border-border bg-muted/50">
						<tr>
							<th class="px-3 py-2 text-left font-medium text-muted-foreground">Device</th>
							{#each selectedPayloadColumns as column}
								<th class="px-3 py-2 text-left font-medium text-muted-foreground">{column}</th>
							{/each}
							<th class="px-3 py-2 text-left font-medium text-muted-foreground">Updated</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-border">
						{#each recentData as record}
							<tr class="bg-background">
								<td class="px-3 py-2 font-medium text-foreground">{record.device}</td>
								{#each selectedPayloadColumns as column}
									<td class="px-3 py-2 text-muted-foreground">{formatValue(record.payload[column])}</td>
								{/each}
								<td class="px-3 py-2 text-muted-foreground whitespace-nowrap">{formatTime(record.timestamp)}</td>
							</tr>
						{:else}
							<tr>
								<td colspan={Math.max(2, selectedPayloadColumns.length + 2)} class="px-3 py-8 text-center text-muted-foreground">
									No realtime production data yet.
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	</div>
</div>
