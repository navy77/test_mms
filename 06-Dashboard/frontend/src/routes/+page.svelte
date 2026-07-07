<script lang="ts">
	import { getStats, devices, machines, alarms } from '$lib/stores/mock.svelte';
	import { Activity, Cpu, HardDrive, Bell, TrendingUp } from '@lucide/svelte';

	const stats = $derived(getStats());

	// Simulated msg/sec sparkline data
	const sparkData = [820, 950, 870, 1020, 980, 1100, 990, 1050, 930, 1000];

	const kpiCards = $derived([
		{
			label: 'Online Devices',
			value: `${stats.onlineDevices} / ${stats.totalDevices}`,
			icon: HardDrive,
			color: 'text-green-500',
			bg: 'bg-green-500/10'
		},
		{
			label: 'Running Machines',
			value: `${stats.runningMachines} / ${machines.length}`,
			icon: Cpu,
			color: 'text-blue-500',
			bg: 'bg-blue-500/10'
		},
		{
			label: 'Active Alarms',
			value: String(stats.activeAlarms),
			icon: Bell,
			color: stats.activeAlarms > 0 ? 'text-red-500' : 'text-green-500',
			bg: stats.activeAlarms > 0 ? 'bg-red-500/10' : 'bg-green-500/10'
		},
		{
			label: 'Avg Msg / sec',
			value: '1,000',
			icon: Activity,
			color: 'text-purple-500',
			bg: 'bg-purple-500/10'
		}
	]);
</script>

<div class="space-y-6">
	<!-- KPI Cards -->
	<div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
		{#each kpiCards as card}
			<div class="rounded-lg border border-border bg-card p-4">
				<div class="flex items-center justify-between">
					<p class="text-xs font-medium text-muted-foreground">{card.label}</p>
					<span class="rounded-md {card.bg} p-1.5">
						<card.icon class="h-3.5 w-3.5 {card.color}" />
					</span>
				</div>
				<p class="mt-2 text-2xl font-semibold text-card-foreground">{card.value}</p>
			</div>
		{/each}
	</div>

	<div class="grid gap-4 lg:grid-cols-2">
		<!-- Active Alarms -->
		<div class="rounded-lg border border-border bg-card p-4">
			<div class="mb-3 flex items-center gap-2">
				<Bell class="h-4 w-4 text-red-500" />
				<h2 class="text-sm font-semibold text-card-foreground">Active Alarms</h2>
			</div>
			<div class="space-y-2">
				{#each alarms.filter((a) => a.state === 'active') as alarm}
					<div class="flex items-start gap-3 rounded-md border border-border bg-background px-3 py-2">
						<span
							class="mt-0.5 h-2 w-2 shrink-0 rounded-full {alarm.severity === 'critical'
								? 'bg-red-500'
								: alarm.severity === 'warning'
									? 'bg-yellow-500'
									: 'bg-blue-500'}"
						></span>
						<div class="min-w-0 flex-1">
							<p class="truncate text-xs font-medium text-foreground">
								{alarm.process} / {alarm.device}
							</p>
							<p class="truncate text-xs text-muted-foreground">{alarm.message}</p>
						</div>
						<span
							class="shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium uppercase {alarm.severity ===
							'critical'
								? 'bg-red-500/10 text-red-600 dark:text-red-400'
								: alarm.severity === 'warning'
									? 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400'
									: 'bg-blue-500/10 text-blue-600 dark:text-blue-400'}"
						>{alarm.severity}</span>
					</div>
				{:else}
					<p class="text-xs text-muted-foreground">No active alarms</p>
				{/each}
			</div>
		</div>

		<!-- Device Overview -->
		<div class="rounded-lg border border-border bg-card p-4">
			<div class="mb-3 flex items-center gap-2">
				<HardDrive class="h-4 w-4 text-blue-500" />
				<h2 class="text-sm font-semibold text-card-foreground">Device Overview</h2>
			</div>
			<div class="space-y-2">
				{#each devices as device}
					<div class="flex items-center gap-3 rounded-md border border-border bg-background px-3 py-2">
						<span
							class="h-2 w-2 shrink-0 rounded-full {device.status === 'online'
								? 'animate-pulse bg-green-500'
								: 'bg-gray-400'}"
						></span>
						<div class="flex min-w-0 flex-1 items-center gap-2">
							<p class="text-xs font-medium text-foreground">{device.process} / {device.device}</p>
							<p class="text-xs text-muted-foreground">{device.mac_id}</p>
						</div>
						<span
							class="text-xs font-medium {device.status === 'online'
								? 'text-green-600 dark:text-green-400'
								: 'text-muted-foreground'}"
						>
							{device.status === 'online' ? `${device.latencyMs}ms` : 'offline'}
						</span>
					</div>
				{/each}
			</div>
		</div>
	</div>

	<!-- Throughput Bar -->
	<div class="rounded-lg border border-border bg-card p-4">
		<div class="mb-3 flex items-center gap-2">
			<TrendingUp class="h-4 w-4 text-purple-500" />
			<h2 class="text-sm font-semibold text-card-foreground">Message Throughput (last 10 cycles)</h2>
		</div>
		<div class="flex h-20 items-end gap-1">
			{#each sparkData as val}
				{@const pct = (val / 1200) * 100}
				<div class="flex flex-1 flex-col items-center gap-1">
					<div
						class="w-full rounded-t-sm bg-primary/70 transition-all duration-500"
						style="height: {pct}%"
					></div>
				</div>
			{/each}
		</div>
		<div class="mt-2 flex justify-between text-[10px] text-muted-foreground">
			<span>0</span>
			<span>1,200 msg/s</span>
		</div>
	</div>
</div>
