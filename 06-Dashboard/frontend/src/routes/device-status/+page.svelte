<script lang="ts">
	import { onDestroy } from 'svelte';
	import { LoaderCircle } from 'lucide-svelte';

	let { data } = $props();

	const processesList = $derived(data.processes || []);
	let selectedProcess = $state('');

	$effect(() => {
		selectedProcess = data.initialProcess || '';
	});
	
	let counts = $state({
		total: 0,
		online: 0,
		offline: 0,
		communication_fail: 0
	});
	let loadingCounts = $state(false);

	let realtimeMap = $state<Record<string, any>>({});
	let sse: EventSource | null = null;

	// Search & Pagination states
	let searchQuery = $state('');
	let currentPage = $state(1);
	const pageSize = 10;

	// Naturally sort devices by device name
	const sortedDevices = $derived(
		[...(data.registeredDevices || [])].sort((a: any, b: any) =>
			a.device.localeCompare(b.device, undefined, { numeric: true })
		)
	);

	const filtered = $derived(
		sortedDevices
			.filter((d: any) => d.process === selectedProcess)
			.filter((d: any) => 
				!searchQuery || 
				d.device.toLowerCase().includes(searchQuery.toLowerCase())
			)
			.map((d: any) => {
				const rt = realtimeMap[d.device];
				return {
					id: d.device,
					process: d.process,
					device: d.device,
					status: rt ? rt.status : 'offline',
					broker: rt ? rt.broker : '—',
					modbus: rt ? rt.modbus : '—',
					mac_id: rt ? rt.mac_id : '—',
					lastSeen: rt ? rt.timestamp : ''
				};
			})
	);

	const paginated = $derived(
		filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize)
	);

	const totalPages = $derived(Math.ceil(filtered.length / pageSize) || 1);

	function connectSSE(proc: string) {
		if (sse) {
			sse.close();
		}
		if (!proc) return;
		
		sse = new EventSource(`http://localhost:8002/api/v1/realtime/mqtt/${proc}`);
		sse.onmessage = (event) => {
			try {
				const list = JSON.parse(event.data);
				const newMap: Record<string, any> = {};
				for (const item of list) {
					let payload = item.payload;
					if (typeof payload === 'string') {
						try {
							payload = JSON.parse(payload);
						} catch {
							payload = {};
						}
					}
					newMap[item.device] = {
						status: item.status || 'offline',
						broker: payload.broker !== undefined ? payload.broker : '—',
						modbus: payload.modbus !== undefined ? payload.modbus : '—',
						mac_id: payload.mac_id || '—',
						timestamp: item.timestamp || ''
					};
				}
				realtimeMap = newMap;
			} catch (err) {
				console.error('Error parsing SSE data:', err);
			}
		};
	}

	async function fetchCounts(proc: string) {
		if (!proc) return;
		loadingCounts = true;
		try {
			const res = await fetch(`http://localhost:8003/api/v1/device/currently/status/${proc}`);
			if (res.ok) {
				const resData = await res.json();
				counts = {
					total: resData.total,
					online: resData.online,
					offline: resData.offline,
					communication_fail: resData.communication_fail
				};
			}
		} catch (err) {
			console.error('Error fetching status counts:', err);
		} finally {
			loadingCounts = false;
		}
	}

	let isFirstRun = true;
	$effect(() => {
		if (selectedProcess) {
			connectSSE(selectedProcess);
			if (isFirstRun) {
				isFirstRun = false;
				return;
			}
			fetchCounts(selectedProcess);
		}
		return () => {
			if (sse) sse.close();
		};
	});

	onDestroy(() => {
		if (sse) sse.close();
	});

	// Reset page to 1 when filters change
	$effect(() => {
		selectedProcess;
		searchQuery;
		currentPage = 1;
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
</script>

<div class="space-y-4">
	<!-- Header with Dropdown -->
	<div class="flex items-center justify-between">
		<h1 class="text-sm font-semibold text-card-foreground">Device Status Overview</h1>
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

	<!-- Summary -->
	<div class="grid grid-cols-4 gap-3 relative">
		{#if loadingCounts}
			<div class="absolute inset-0 bg-background/50 flex items-center justify-center z-10 rounded-lg">
				<LoaderCircle class="h-5 w-5 animate-spin text-primary" />
			</div>
		{/if}
		<div class="rounded-lg border border-border bg-card p-3">
			<p class="text-xs text-muted-foreground">Total Devices</p>
			<p class="text-3xl font-semibold text-card-foreground">{counts.total}</p>
		</div>
		<div class="rounded-lg border border-border bg-card p-3">
			<p class="text-xs text-muted-foreground">Online</p>
			<p class="text-3xl font-semibold text-green-500">{counts.online}</p>
		</div>
		<div class="rounded-lg border border-border bg-card p-3">
			<p class="text-xs text-muted-foreground">Offline</p>
			<p class="text-3xl font-semibold {counts.offline > 0 ? 'text-red-500' : 'text-green-500'}">{counts.offline}</p>
		</div>
		<div class="rounded-lg border border-border bg-card p-3">
			<p class="text-xs text-muted-foreground">Communication Fail</p>
			<p class="text-3xl font-semibold {counts.communication_fail > 0 ? 'text-amber-500' : 'text-yellow-500'}">{counts.communication_fail}</p>
		</div>
	</div>

	<!-- Search Input Bar -->
	<div class="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-2 bg-muted/10">
		<input
			type="text"
			bind:value={searchQuery}
			placeholder="Search by device name..."
			class="flex-1 max-w-sm rounded border border-border bg-background px-3 py-1.5 text-xs text-foreground outline-none focus:border-primary placeholder:text-muted-foreground"
		/>
	</div>

	<!-- Device Table -->
	<div class="rounded-lg border border-border bg-card overflow-hidden">
		<table class="w-full text-xs">
			<thead class="border-b border-border bg-muted/50">
				<tr>
					<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Status</th>
					<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Process</th>
					<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Device</th>
					<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">MAC ID</th>
					<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Broker</th>
					<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Modbus</th>
					<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Last Seen</th>
				</tr>
			</thead>
			<tbody class="divide-y divide-border">
				{#each paginated as device (device.id)}
					<tr class="hover:bg-muted/30 transition-colors">
						<td class="px-4 py-2.5">
							<div class="flex items-center gap-1.5">
								<span class="h-2 w-2 rounded-full {device.status === 'online' ? 'animate-pulse bg-green-500' : 'bg-gray-400'}"></span>
								<span class="{device.status === 'online' ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground'} font-medium">
									{device.status}
								</span>
							</div>
						</td>
						<td class="px-4 py-2.5 font-medium text-foreground">{device.process}</td>
						<td class="px-4 py-2.5 text-foreground">{device.device}</td>
						<td class="px-4 py-2.5 font-mono text-muted-foreground">{device.mac_id}</td>
						<td class="px-4 py-2.5">
							{#if device.broker === '—'}
								<span class="text-muted-foreground">—</span>
							{:else if String(device.broker) === '1'}
								<span class="text-green-600 dark:text-green-400 font-medium">OK</span>
							{:else}
								<span class="text-red-600 dark:text-red-400 font-medium">FAIL</span>
							{/if}
						</td>
						<td class="px-4 py-2.5">
							{#if device.modbus === '—'}
								<span class="text-muted-foreground">—</span>
							{:else if String(device.modbus) === '1'}
								<span class="text-green-600 dark:text-green-400 font-medium">OK</span>
							{:else}
								<span class="text-red-600 dark:text-red-400 font-medium">FAIL</span>
							{/if}
						</td>
						<td class="px-4 py-2.5 text-muted-foreground whitespace-nowrap">{formatTime(device.lastSeen)}</td>
					</tr>
				{:else}
					<tr>
						<td colspan="7" class="px-4 py-8 text-center text-muted-foreground">No devices found for this process</td>
					</tr>
				{/each}
			</tbody>
		</table>

		<!-- Pagination Footer -->
		<div class="flex items-center justify-between border-t border-border px-4 py-2.5 bg-muted/20">
			<p class="text-xs text-muted-foreground">
				Showing {filtered.length > 0 ? (currentPage - 1) * pageSize + 1 : 0} to {Math.min(currentPage * pageSize, filtered.length)} of {filtered.length} rows
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
	</div>
</div>
