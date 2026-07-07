<script lang="ts">
	import { machines } from '$lib/stores/mock.svelte';
	import type { MachineStatus } from '$lib/stores/mock.svelte';

	const statusConfig: Record<MachineStatus, { label: string; dot: string; card: string }> = {
		running: { label: 'Running', dot: 'bg-green-500 animate-pulse', card: 'border-green-500/30 bg-green-500/5' },
		idle:    { label: 'Idle',    dot: 'bg-yellow-400',              card: 'border-yellow-400/30 bg-yellow-400/5' },
		stopped: { label: 'Stopped', dot: 'bg-red-500',                 card: 'border-red-500/30 bg-red-500/5' },
		offline: { label: 'Offline', dot: 'bg-gray-400',                card: 'border-border bg-muted/30' }
	};

	const summary = $derived({
		running: machines.filter((m) => m.status === 'running').length,
		idle:    machines.filter((m) => m.status === 'idle').length,
		stopped: machines.filter((m) => m.status === 'stopped').length,
		offline: machines.filter((m) => m.status === 'offline').length
	});
</script>

<div class="space-y-6">
	<!-- Summary Row -->
	<div class="grid grid-cols-4 gap-3">
		{#each Object.entries(summary) as [status, count]}
			{@const cfg = statusConfig[status as MachineStatus]}
			<div class="rounded-lg border border-border bg-card p-3 text-center">
				<div class="flex items-center justify-center gap-1.5">
					<span class="h-2 w-2 rounded-full {cfg.dot}"></span>
					<span class="text-xs text-muted-foreground">{cfg.label}</span>
				</div>
				<p class="mt-1 text-2xl font-semibold text-card-foreground">{count}</p>
			</div>
		{/each}
	</div>

	<!-- Machine Grid -->
	<div class="grid grid-cols-2 gap-3 lg:grid-cols-3">
		{#each machines as machine}
			{@const cfg = statusConfig[machine.status]}
			<div class="rounded-lg border {cfg.card} p-4 transition-all hover:shadow-sm">
				<!-- Header -->
				<div class="flex items-center justify-between">
					<div class="flex items-center gap-2">
						<span class="h-2.5 w-2.5 rounded-full {cfg.dot}"></span>
						<p class="text-sm font-semibold text-foreground">{machine.name}</p>
					</div>
					<span class="rounded-full border border-border px-2 py-0.5 text-[10px] font-medium uppercase text-muted-foreground">
						{machine.process}
					</span>
				</div>

				<!-- Status Badge -->
				<p class="mt-1 text-xs font-medium {machine.status === 'running' ? 'text-green-600 dark:text-green-400' : machine.status === 'idle' ? 'text-yellow-600 dark:text-yellow-400' : machine.status === 'stopped' ? 'text-red-600 dark:text-red-400' : 'text-muted-foreground'}">
					{cfg.label}
				</p>

				<!-- Data Grid -->
				{#if machine.status !== 'offline'}
					<div class="mt-3 grid grid-cols-3 gap-2">
						{#each [1, 2, 3] as i}
							<div class="rounded bg-background p-1.5 text-center">
								<p class="text-[9px] text-muted-foreground">data{i}</p>
								<p class="text-xs font-semibold text-foreground">{machine[`data${i}` as keyof typeof machine]}</p>
							</div>
						{/each}
					</div>
				{/if}

				<!-- Uptime -->
				<p class="mt-2 text-[10px] text-muted-foreground">Uptime: {machine.uptime}</p>
			</div>
		{/each}
	</div>
</div>
