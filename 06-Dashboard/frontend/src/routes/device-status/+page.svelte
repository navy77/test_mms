<script lang="ts">
	import { devices } from '$lib/stores/mock.svelte';

	let processFilter = $state('all');
	const processes = $derived(['all', ...new Set(devices.map((d) => d.process))]);
	const filtered = $derived(
		devices.filter((d) => processFilter === 'all' || d.process === processFilter)
	);

	const onlineCount = $derived(devices.filter((d) => d.status === 'online').length);
	const offlineCount = $derived(devices.filter((d) => d.status === 'offline').length);

	function formatTime(ts: string) {
		return new Date(ts).toLocaleString('th-TH', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short' });
	}
</script>

<div class="space-y-4">
	<!-- Summary -->
	<div class="grid grid-cols-3 gap-3">
		<div class="rounded-lg border border-border bg-card p-3">
			<p class="text-xs text-muted-foreground">Total Devices</p>
			<p class="text-2xl font-semibold text-card-foreground">{devices.length}</p>
		</div>
		<div class="rounded-lg border border-border bg-card p-3">
			<p class="text-xs text-muted-foreground">Online</p>
			<p class="text-2xl font-semibold text-green-500">{onlineCount}</p>
		</div>
		<div class="rounded-lg border border-border bg-card p-3">
			<p class="text-xs text-muted-foreground">Offline</p>
			<p class="text-2xl font-semibold {offlineCount > 0 ? 'text-red-500' : 'text-green-500'}">{offlineCount}</p>
		</div>
	</div>

	<!-- Filter -->
	<div class="flex items-center gap-2">
		<span class="text-xs text-muted-foreground">Process:</span>
		{#each processes as p}
			<button
				onclick={() => (processFilter = p)}
				class="rounded-full px-3 py-1 text-xs transition-colors {processFilter === p
					? 'bg-primary text-primary-foreground'
					: 'border border-border text-muted-foreground hover:bg-muted'}"
			>{p}</button>
		{/each}
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
					<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Latency</th>
					<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Last Seen</th>
				</tr>
			</thead>
			<tbody class="divide-y divide-border">
				{#each filtered as device (device.id)}
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
						<td class="px-4 py-2.5 text-muted-foreground">{device.broker}</td>
						<td class="px-4 py-2.5 text-muted-foreground">{device.modbus}</td>
						<td class="px-4 py-2.5 {device.status === 'online' ? 'text-foreground' : 'text-muted-foreground'}">
							{device.status === 'online' ? `${device.latencyMs} ms` : '—'}
						</td>
						<td class="px-4 py-2.5 text-muted-foreground whitespace-nowrap">{formatTime(device.lastSeen)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>
