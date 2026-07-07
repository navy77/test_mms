<script lang="ts">
	import { alarms } from '$lib/stores/mock.svelte';
	import type { AlarmSeverity, AlarmState } from '$lib/stores/mock.svelte';

	let filter = $state<'all' | AlarmState>('all');
	let severityFilter = $state<'all' | AlarmSeverity>('all');

	const filtered = $derived(
		alarms.filter((a) => {
			const stateOk = filter === 'all' || a.state === filter;
			const sevOk = severityFilter === 'all' || a.severity === severityFilter;
			return stateOk && sevOk;
		})
	);

	const activeCount = $derived(alarms.filter((a) => a.state === 'active').length);
	const criticalCount = $derived(alarms.filter((a) => a.severity === 'critical' && a.state === 'active').length);

	function acknowledge(id: string) {
		const alarm = alarms.find((a) => a.id === id);
		if (alarm) alarm.state = 'cleared';
	}

	function severityColor(s: AlarmSeverity) {
		return s === 'critical' ? 'text-red-600 dark:text-red-400 bg-red-500/10'
			: s === 'warning'  ? 'text-yellow-600 dark:text-yellow-400 bg-yellow-500/10'
			:                    'text-blue-600 dark:text-blue-400 bg-blue-500/10';
	}

	function dotColor(s: AlarmSeverity) {
		return s === 'critical' ? 'bg-red-500' : s === 'warning' ? 'bg-yellow-500' : 'bg-blue-500';
	}

	function formatTime(ts: string) {
		return new Date(ts).toLocaleString('th-TH', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short' });
	}
</script>

<div class="space-y-4">
	<!-- Summary -->
	<div class="grid grid-cols-3 gap-3">
		<div class="rounded-lg border border-border bg-card p-3">
			<p class="text-xs text-muted-foreground">Active Alarms</p>
			<p class="text-2xl font-semibold {activeCount > 0 ? 'text-red-500' : 'text-green-500'}">{activeCount}</p>
		</div>
		<div class="rounded-lg border border-border bg-card p-3">
			<p class="text-xs text-muted-foreground">Critical</p>
			<p class="text-2xl font-semibold {criticalCount > 0 ? 'text-red-500' : 'text-green-500'}">{criticalCount}</p>
		</div>
		<div class="rounded-lg border border-border bg-card p-3">
			<p class="text-xs text-muted-foreground">Total Logged</p>
			<p class="text-2xl font-semibold text-card-foreground">{alarms.length}</p>
		</div>
	</div>

	<!-- Filters -->
	<div class="flex items-center gap-2">
		<span class="text-xs text-muted-foreground">State:</span>
		{#each ['all', 'active', 'cleared'] as f}
			<button
				onclick={() => (filter = f as typeof filter)}
				class="rounded-full px-3 py-1 text-xs transition-colors {filter === f
					? 'bg-primary text-primary-foreground'
					: 'border border-border text-muted-foreground hover:bg-muted'}"
			>{f}</button>
		{/each}
		<span class="ml-4 text-xs text-muted-foreground">Severity:</span>
		{#each ['all', 'critical', 'warning', 'info'] as s}
			<button
				onclick={() => (severityFilter = s as typeof severityFilter)}
				class="rounded-full px-3 py-1 text-xs transition-colors {severityFilter === s
					? 'bg-primary text-primary-foreground'
					: 'border border-border text-muted-foreground hover:bg-muted'}"
			>{s}</button>
		{/each}
	</div>

	<!-- Table -->
	<div class="rounded-lg border border-border bg-card overflow-hidden">
		<table class="w-full text-xs">
			<thead class="border-b border-border bg-muted/50">
				<tr>
					<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Severity</th>
					<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Process / Device</th>
					<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Message</th>
					<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Time</th>
					<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">State</th>
					<th class="px-4 py-2.5 text-left font-medium text-muted-foreground"></th>
				</tr>
			</thead>
			<tbody class="divide-y divide-border">
				{#each filtered as alarm (alarm.id)}
					<tr class="hover:bg-muted/30 transition-colors">
						<td class="px-4 py-2.5">
							<div class="flex items-center gap-1.5">
								<span class="h-1.5 w-1.5 rounded-full {dotColor(alarm.severity)}"></span>
								<span class="rounded px-1.5 py-0.5 text-[10px] font-medium uppercase {severityColor(alarm.severity)}">
									{alarm.severity}
								</span>
							</div>
						</td>
						<td class="px-4 py-2.5 font-medium text-foreground">{alarm.process} / {alarm.device}</td>
						<td class="px-4 py-2.5 text-muted-foreground max-w-xs truncate">{alarm.message}</td>
						<td class="px-4 py-2.5 text-muted-foreground whitespace-nowrap">{formatTime(alarm.timestamp)}</td>
						<td class="px-4 py-2.5">
							<span class="rounded-full px-2 py-0.5 text-[10px] font-medium {alarm.state === 'active' ? 'bg-red-500/10 text-red-600 dark:text-red-400' : 'bg-green-500/10 text-green-600 dark:text-green-400'}">
								{alarm.state}
							</span>
						</td>
						<td class="px-4 py-2.5">
							{#if alarm.state === 'active'}
								<button
									onclick={() => acknowledge(alarm.id)}
									class="rounded border border-border px-2 py-0.5 text-[10px] text-muted-foreground hover:bg-muted transition-colors"
								>Ack</button>
							{/if}
						</td>
					</tr>
				{:else}
					<tr>
						<td colspan="6" class="px-4 py-8 text-center text-muted-foreground">No alarms found</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>
