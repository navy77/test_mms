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

	// All devices for the selected process, sorted
	const activeDevices = $derived(
		(data.registeredDevices || [])
			.filter((d: any) => d.process === selectedProcess)
			.sort((a: any, b: any) => a.device.localeCompare(b.device, undefined, { numeric: true }))
	);

	// ── Device selection states ──────────────────────────────────────────────
	let selectedDevices = $state<string[]>([]);
	let selectExpanded = $state(false);

	// Auto-select the first 12 devices when selectedProcess changes
	$effect(() => {
		if (selectedProcess) {
			const devicesOfProcess = activeDevices.map((d: any) => d.device);
			selectedDevices = devicesOfProcess.slice(0, 12);
		}
	});

	// Devices that should be displayed
	const displayedDevices = $derived(
		activeDevices.filter((d: any) => selectedDevices.includes(d.device))
	);

	// ── Polling logic for process daily data ────────────────────────────────
	let dailyRecords = $state<any[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let pollInterval: any = null;

	async function fetchProcessDailyData(processName: string) {
		if (!processName) return;
		loading = dailyRecords.length === 0;
		error = null;
		try {
			const apiHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
			const res = await fetch(`http://${apiHost}:8003/api/v1/status/daily/${processName}`);
			if (!res.ok) {
				throw new Error(`Failed to fetch daily process status (${res.status})`);
			}
			const json = await res.json();
			dailyRecords = Array.isArray(json) ? json : [];
			error = null;
		} catch (e: any) {
			console.error("Error in fetchProcessDailyData:", e);
			if (dailyRecords.length === 0) {
				error = e.message || "Failed to load history data";
			}
		} finally {
			loading = false;
		}
	}
	$effect(() => {
		if (selectedProcess) {
			fetchProcessDailyData(selectedProcess);
			if (pollInterval) clearInterval(pollInterval);
			pollInterval = setInterval(() => {
				fetchProcessDailyData(selectedProcess);
			}, 30000); // 30 seconds interval
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
	<!-- Header -->
	<div class="flex items-center justify-between">
		<h1 class="text-sm font-semibold text-card-foreground">Machine Utilization</h1>
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
			<span class="w-6 h-0.5 rounded" style="background-color: #16537e"></span>
			<span>Utilize %</span>
		</div>
	</div>

	<!-- Select Machine (Collapsible) -->
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

	<!-- Grid of devices -->
	{#if activeDevices.length === 0}
		<div class="rounded-lg border border-dashed p-12 text-center">
			<p class="text-sm text-muted-foreground">
				No devices registered for this process.
			</p>
		</div>
	{:else if displayedDevices.length === 0}
		<div class="rounded-lg border border-dashed p-12 text-center bg-card">
			<p class="text-sm text-muted-foreground">
				Please select at least one device above to monitor.
			</p>
		</div>
	{:else}
		<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
			{#each displayedDevices as dev (dev.device)}
				{@const deviceRecords = dailyRecords.filter((r) => r.device === dev.device)}
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
						<HistoryChart 
							process={selectedProcess} 
							device={dev.device} 
							{colorMap} 
							records={deviceRecords}
							loading={loading}
							error={error}
						/>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
