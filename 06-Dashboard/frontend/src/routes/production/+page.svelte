<script lang="ts">
	import { machines } from '$lib/stores/mock.svelte';
	import { BarChart2 } from '@lucide/svelte';

	// Simulated hourly production data
	const hourlyData = [
		{ hour: '07:00', output: 480 },
		{ hour: '08:00', output: 512 },
		{ hour: '09:00', output: 498 },
		{ hour: '10:00', output: 531 },
		{ hour: '11:00', output: 520 },
		{ hour: '12:00', output: 310 },
		{ hour: '13:00', output: 488 },
		{ hour: '14:00', output: 505 },
		{ hour: '15:00', output: 516 },
		{ hour: '16:00 (now)', output: 200 }
	];

	const maxOutput = Math.max(...hourlyData.map((d) => d.output));
	const totalToday = hourlyData.reduce((s, d) => s + d.output, 0);
	const target = 4800;
	const efficiency = Math.round((totalToday / target) * 100);

	const runningMachines = $derived(machines.filter((m) => m.status === 'running'));
</script>

<div class="space-y-6">
	<!-- Summary Cards -->
	<div class="grid grid-cols-3 gap-4">
		<div class="rounded-lg border border-border bg-card p-4">
			<p class="text-xs text-muted-foreground">Total Output Today</p>
			<p class="mt-1 text-2xl font-semibold text-card-foreground">{totalToday.toLocaleString()}</p>
			<p class="text-xs text-muted-foreground">units</p>
		</div>
		<div class="rounded-lg border border-border bg-card p-4">
			<p class="text-xs text-muted-foreground">Target</p>
			<p class="mt-1 text-2xl font-semibold text-card-foreground">{target.toLocaleString()}</p>
			<p class="text-xs text-muted-foreground">units / shift</p>
		</div>
		<div class="rounded-lg border border-border bg-card p-4">
			<p class="text-xs text-muted-foreground">Efficiency</p>
			<p class="mt-1 text-2xl font-semibold {efficiency >= 90 ? 'text-green-500' : efficiency >= 70 ? 'text-yellow-500' : 'text-red-500'}">{efficiency}%</p>
			<div class="mt-2 h-1.5 w-full rounded-full bg-muted">
				<div class="h-1.5 rounded-full bg-primary transition-all" style="width: {efficiency}%"></div>
			</div>
		</div>
	</div>

	<!-- Hourly Output Chart -->
	<div class="rounded-lg border border-border bg-card p-4">
		<div class="mb-4 flex items-center gap-2">
			<BarChart2 class="h-4 w-4 text-primary" />
			<h2 class="text-sm font-semibold text-card-foreground">Hourly Output (07:00 – now)</h2>
		</div>
		<div class="flex h-40 items-end gap-2">
			{#each hourlyData as d}
				{@const pct = (d.output / maxOutput) * 100}
				<div class="group flex flex-1 flex-col items-center gap-1">
					<span class="hidden text-[9px] text-muted-foreground group-hover:block">{d.output}</span>
					<div
						class="w-full rounded-t bg-primary/80 hover:bg-primary transition-all duration-300"
						style="height: {pct}%"
					></div>
					<span class="text-[9px] text-muted-foreground" style="writing-mode: vertical-lr; transform: rotate(180deg); height: 36px;">{d.hour}</span>
				</div>
			{/each}
		</div>
	</div>

	<!-- Running Machines Data -->
	<div class="rounded-lg border border-border bg-card p-4">
		<h2 class="mb-3 text-sm font-semibold text-card-foreground">Running Machine Details</h2>
		<div class="overflow-x-auto">
			<table class="w-full text-xs">
				<thead>
					<tr class="border-b border-border">
						<th class="pb-2 text-left font-medium text-muted-foreground">Machine</th>
						<th class="pb-2 text-right font-medium text-muted-foreground">Data 1</th>
						<th class="pb-2 text-right font-medium text-muted-foreground">Data 2</th>
						<th class="pb-2 text-right font-medium text-muted-foreground">Data 3</th>
						<th class="pb-2 text-right font-medium text-muted-foreground">Uptime</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-border">
					{#each runningMachines as m}
						<tr>
							<td class="py-2 font-medium text-foreground">{m.name}</td>
							<td class="py-2 text-right text-foreground">{m.data1}</td>
							<td class="py-2 text-right text-foreground">{m.data2}</td>
							<td class="py-2 text-right text-foreground">{m.data3}</td>
							<td class="py-2 text-right text-muted-foreground">{m.uptime}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>
</div>
