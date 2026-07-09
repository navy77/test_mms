<script lang="ts">
	import HistoryChart from "$lib/components/HistoryChart.svelte";

	let { data } = $props();

	const processesList = $derived(data.processes || []);
	let selectedProcess = $state('');

	$effect(() => {
		selectedProcess = data.initialProcess || '';
	});

	const colorMap = $derived.by(() => {
		const map: Record<string, string> = {};

		const activeStatuses = (data.statuses || []).filter((s: any) => s.process === selectedProcess);
		for (const s of activeStatuses) {
			map[s.status] = s.color;
		}

		// Fallbacks
		const standards: Record<string, string> = {
			run: "#22c55e",
			alarm: "#ef4444",
			wait: "#eab308",
			stop: "#6b7280",
			other: "#3b82f6",
			offline: "#9ca3af",
			"no data": "#EBECEF"
		};
		for (const [k, v] of Object.entries(standards)) {
			if (!(k in map)) map[k] = v;
		}

		return map;
	});

	// All devices for the selected process, sorted, capped at 20
	const activeDevices = $derived(
		(data.registeredDevices || [])
			.filter((d: any) => d.process === selectedProcess)
			.sort((a: any, b: any) => a.device.localeCompare(b.device, undefined, { numeric: true }))
			.slice(0, 16)
	);
</script>

<div class="space-y-5">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<h1 class="text-sm font-semibold text-card-foreground">Machine Status History</h1>
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

	<!-- Status Color Legend -->
	<div class="flex flex-wrap items-center gap-4 px-4 py-2 border border-border rounded-lg bg-card text-xs">
		<span class="font-medium text-muted-foreground">Legend:</span>
		{#each Object.entries(colorMap) as [status, color]}
			{#if status !== "no data"}
				<div class="flex items-center gap-1.5 capitalize text-muted-foreground">
					<span class="w-3 h-3 rounded-sm" style="background-color: {color}"></span>
					<span>{status}</span>
				</div>
			{/if}
		{/each}
		<!-- Utilize legend entry -->
		<div class="flex items-center gap-1.5 text-muted-foreground">
			<span class="w-6 h-0.5 rounded" style="background-color: #a78bfa"></span>
			<span>Utilize %</span>
		</div>
	</div>

	<!-- Grid of devices -->
	{#if activeDevices.length === 0}
		<div class="rounded-lg border border-dashed p-12 text-center">
			<p class="text-sm text-muted-foreground">
				No devices registered for this process.
			</p>
		</div>
	{:else}
		<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
			{#each activeDevices as dev (dev.device)}
				<div class="rounded-lg border border-border bg-card overflow-hidden hover:shadow-md transition-all duration-200">
					<!-- Card Header -->
					<div class="flex items-center justify-between px-3 py-2 border-b border-border/60">
						<div class="flex items-center gap-1.5 min-w-0">
							<span class="h-1.5 w-1.5 rounded-full bg-primary flex-shrink-0 animate-pulse"></span>
							<h3 class="text-xs font-semibold text-foreground truncate">{dev.device}</h3>
						</div>
						<span class="text-[9px] font-medium uppercase text-muted-foreground border border-border/60 rounded px-1 py-0.5 flex-shrink-0">
							{selectedProcess}
						</span>
					</div>
					<!-- History Chart -->
					<div class="px-1 py-1">
						<HistoryChart process={selectedProcess} device={dev.device} {colorMap} />
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
