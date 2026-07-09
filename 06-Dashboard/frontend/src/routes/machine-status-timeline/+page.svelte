<script lang="ts">
	import TimelineChart from '$lib/components/TimelineChart.svelte';

	let { data } = $props();

	const processesList = $derived(data.processes || []);
	let selectedProcess = $state('');

	$effect(() => {
		selectedProcess = data.initialProcess || '';
	});

	const colorMap = $derived.by(() => {
		const map: Record<string, string> = {};
		
		// Fill map with registered statuses and colors from ClickHouse
		const activeStatuses = (data.statuses || []).filter((s: any) => s.process === selectedProcess);
		for (const s of activeStatuses) {
			map[s.status] = s.color;
		}

		// Fallbacks for standard values if not defined in the database
		const standards: Record<string, string> = {
			run: '#22c55e',
			alarm: '#ef4444',
			wait: '#eab308',
			stop: '#6b7280',
			other: '#3b82f6',
			offline: '#9ca3af',
			'no data': '#EBECEF'
		};
		for (const [k, v] of Object.entries(standards)) {
			if (!(k in map)) {
				map[k] = v;
			}
		}

		return map;
	});

	const activeDevices = $derived(
		(data.registeredDevices || [])
			.filter((d: any) => d.process === selectedProcess)
			.sort((a: any, b: any) => a.device.localeCompare(b.device, undefined, { numeric: true }))
	);

	let selectedDevices = $state<string[]>([]);
	let selectExpanded = $state(false); // Default collapsed to keep the view clean

	// Auto-select first 5 devices when activeDevices loads
	$effect(() => {
		if (activeDevices.length > 0 && selectedDevices.length === 0) {
			selectedDevices = activeDevices.slice(0, 5).map((d: any) => d.device);
		}
	});

	// Reset selection when process changes
	$effect(() => {
		selectedProcess;
		selectedDevices = [];
	});
</script>

<div class="space-y-6">
	<!-- Header with Dropdown -->
	<div class="flex items-center justify-between">
		<h1 class="text-sm font-semibold text-card-foreground">Machine Status Timeline</h1>
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

	<!-- Select Machine (Collapsible) -->
	<div class="rounded-lg border border-border bg-card overflow-hidden">
		<button 
			type="button"
			onclick={() => (selectExpanded = !selectExpanded)}
			class="w-full flex items-center justify-between px-4 py-3 text-xs font-semibold text-card-foreground hover:bg-muted/30 transition-colors"
		>
			<span>Select Machines to Monitor (Max 5)</span>
			<div class="flex items-center gap-2 text-muted-foreground font-normal">
				<span>{selectedDevices.length} / 5 selected</span>
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
								disabled={!isChecked && selectedDevices.length >= 5}
								onchange={(e) => {
									if (e.currentTarget.checked) {
										if (selectedDevices.length < 5) {
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

	<!-- Status Color Legend -->
	<div class="flex flex-wrap items-center gap-4 px-4 py-2 border border-border rounded-lg bg-card text-xs">
		<span class="font-medium text-muted-foreground">Legend:</span>
		{#each Object.entries(colorMap) as [status, color]}
			{#if status !== 'no data'}
				<div class="flex items-center gap-1.5 capitalize text-muted-foreground">
					<span class="w-3 h-3 rounded-full" style="background-color: {color}"></span>
					<span>{status}</span>
				</div>
			{/if}
		{/each}
	</div>

	<!-- Chart List (up to 5 rows) -->
	<div class="space-y-4">
		{#if selectedDevices.length === 0}
			<div class="rounded-lg border border-dashed p-12 text-center">
				<p class="text-sm text-muted-foreground">No machines selected. Please select up to 5 machines to display timelines.</p>
			</div>
		{:else}
			{#each selectedDevices as dev}
				<div class="rounded-lg border border-border bg-card p-2 px-4 hover:shadow-sm transition-all duration-200 flex items-center gap-6">
					<!-- Machine Info (Left side, fixed width) -->
					<div class="w-32 shrink-0 flex flex-col gap-1">
						<div class="flex items-center gap-1.5">
							<span class="h-2 w-2 rounded-full bg-primary animate-pulse"></span>
							<h3 class="text-xs font-semibold text-foreground tracking-tight">{dev}</h3>
						</div>
						<span class="w-fit rounded border border-border px-1.5 py-0.5 text-[9px] font-medium uppercase text-muted-foreground">
							{selectedProcess}
						</span>
					</div>

					<!-- Timeline Chart (Right side, fills remaining space) -->
					<div class="flex-1 min-w-0">
						<TimelineChart process={selectedProcess} device={dev} {colorMap} />
					</div>
				</div>
			{/each}
		{/if}
	</div>
</div>
