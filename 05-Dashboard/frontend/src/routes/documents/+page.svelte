<script lang="ts">
	import { BookOpen, Key, Link2, Copy, Check, Terminal, Info, Eye, EyeOff } from '@lucide/svelte';
	import { fade } from 'svelte/transition';

	// Copied state mapping
	let copiedId = $state<string | null>(null);
	let showApiKey = $state(false);

	function copyToClipboard(text: string, id: string) {
		navigator.clipboard.writeText(text);
		copiedId = id;
		setTimeout(() => {
			if (copiedId === id) copiedId = null;
		}, 2000);
	}

	const apis = [
		{
			title: 'Production Data APIs',
			description: 'Retrieve raw sensor payloads and production metrics from clickhouse tables.',
			endpoints: [
				{
					path: '/mic/api/v1/data/currently/{process}',
					method: 'GET',
					desc: 'Get live production payloads from 07:00 AM to current hour.',
					curl: 'curl -i -H "apikey: [secret key]" "http://[serverIP]:8500/mic/api/v1/data/currently/demo1?devices=no_1,no_2"'
				},
				{
					path: '/mic/api/v1/data/daily/{process}',
					method: 'GET',
					desc: 'Get daily data aggregates starting from 1st of the current month.',
					curl: 'curl -i -H "apikey: [secret key]" "http://[serverIP]:8500/mic/api/v1/data/daily/demo1?devices=no_1,no_2"'
				},
				{
					path: '/mic/api/v1/data/monthly/{year}/{month}/{process}',
					method: 'GET',
					desc: 'Get monthly summary for a specific year and month.',
					curl: 'curl -i -H "apikey: [secret key]" "http://[serverIP]:8500/mic/api/v1/data/monthly/2026/07/demo1"'
				}
			]
		},
		{
			title: 'Machine Status APIs',
			description: 'Retrieve operational status logs and duration calculations.',
			endpoints: [
				{
					path: '/mic/api/v1/status/currently/{process}',
					method: 'GET',
					desc: 'Get status logs from 07:00 AM to current hour.',
					curl: 'curl -i -H "apikey: [secret key]" "http://[serverIP]:8500/mic/api/v1/status/currently/demo1?devices=no_1,no_2"'
				},
				{
					path: '/mic/api/v1/status/daily/{process}',
					method: 'GET',
					desc: 'Get daily status logs starting from 1st of the current month.',
					curl: 'curl -i -H "apikey: [secret key]" "http://[serverIP]:8500/mic/api/v1/status/daily/demo1?devices=no_1,no_2"'
				},
				{
					path: '/mic/api/v1/status/monthly/{year}/{month}/{process}',
					method: 'GET',
					desc: 'Get monthly status logs for a specific year and month.',
					curl: 'curl -i -H "apikey: [secret key]" "http://[serverIP]:8500/mic/api/v1/status/monthly/2026/07/demo1"'
				}
			]
		},
		{
			title: 'Alarm Logs APIs',
			description: 'Query machine malfunction and warning triggers.',
			endpoints: [
				{
					path: '/mic/api/v1/alarm/currently/{process}',
					method: 'GET',
					desc: 'Get live alarm logs from 07:00 AM to current hour.',
					curl: 'curl -i -H "apikey: [secret key]" "http://[serverIP]:8500/mic/api/v1/alarm/currently/demo1?devices=no_1,no_2"'
				},
				{
					path: '/mic/api/v1/alarm/daily/{process}',
					method: 'GET',
					desc: 'Get daily alarm logs starting from 1st of the current month.',
					curl: 'curl -i -H "apikey: [secret key]" "http://[serverIP]:8500/mic/api/v1/alarm/daily/demo1?devices=no_1,no_2"'
				},
				{
					path: '/mic/api/v1/alarm/monthly/{year}/{month}/{process}',
					method: 'GET',
					desc: 'Get monthly alarm logs for a specific year and month.',
					curl: 'curl -i -H "apikey: [secret key]" "http://[serverIP]:8500/mic/api/v1/alarm/monthly/2026/07/demo1"'
				}
			]
		},
		{
			title: 'Device Connectivity APIs',
			description: 'Query device health, online metrics, and availability indexes.',
			endpoints: [
				{
					path: '/mic/api/v1/device/currently/{process}',
					method: 'GET',
					desc: 'Get live device availability logs from 07:00 AM to current hour.',
					curl: 'curl -i -H "apikey: [secret key]" "http://[serverIP]:8500/mic/api/v1/device/currently/demo1?devices=no_1,no_2"'
				},
				{
					path: '/mic/api/v1/device/daily/{process}',
					method: 'GET',
					desc: 'Get daily availability logs starting from 1st of the current month.',
					curl: 'curl -i -H "apikey: [secret key]" "http://[serverIP]:8500/mic/api/v1/device/daily/demo1?devices=no_1,no_2"'
				},
				{
					path: '/mic/api/v1/device/monthly/{year}/{month}/{process}',
					method: 'GET',
					desc: 'Get monthly availability logs for a specific year and month.',
					curl: 'curl -i -H "apikey: [secret key]" "http://[serverIP]:8500/mic/api/v1/device/monthly/2026/07/demo1"'
				}
			]
		}
	];
</script>

<div class="space-y-6">
	<!-- Page Header -->
	<div class="flex items-center gap-3">
		<div class="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
			<BookOpen class="h-5 w-5" />
		</div>
		<div>
			<h1 class="text-lg font-bold text-foreground">API Reference Documents</h1>
			<p class="text-xs text-muted-foreground">Developer guidelines for querying the ClickHouse OLAP endpoints via Kong Gateway.</p>
		</div>
	</div>

	<!-- Authentication & Setup Info Card -->
	<div class="rounded-lg border border-border bg-card p-5 relative overflow-hidden">
		<div class="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full blur-2xl pointer-events-none"></div>
		
		<div class="flex items-center gap-2 mb-4">
			<Key class="h-4.5 w-4.5 text-primary" />
			<h2 class="text-sm font-semibold text-foreground">Gateway Authentication (Key-Auth)</h2>
		</div>

		<div class="grid md:grid-cols-2 gap-6 text-xs text-muted-foreground leading-relaxed">

		
			<div class="space-y-3 bg-background/50 rounded-lg p-4 border border-border">
				<div class="flex items-center justify-between">
					<span class="font-semibold text-foreground">Access Details:</span>
					<span class="text-[10px] text-green-500 bg-green-500/10 px-2 py-0.5 rounded font-mono">SECURE</span>
				</div>
				<div class="grid grid-cols-3 gap-2 border-t border-border/50 pt-2">
					<span class="font-medium text-foreground">Gateway IP:</span>
					<span class="col-span-2 text-right font-mono">http://[serverIP]:8500</span>
					
					<span class="font-medium text-foreground">Header Key:</span>
					<span class="col-span-2 text-right font-mono">apikey</span>

					<span class="font-medium text-foreground">Header Value:</span>
					<div class="col-span-2 flex items-center justify-end gap-1.5 font-mono">
						<span class="font-bold text-foreground">
							{showApiKey ? 'sawadeeja' : '•••••••••'}
						</span>
						<button
							onclick={() => showApiKey = !showApiKey}
							class="text-muted-foreground hover:text-foreground transition-colors p-0.5"
							title={showApiKey ? "Hide API key" : "Show API key"}
						>
							{#if showApiKey}
								<EyeOff class="h-3.5 w-3.5" />
							{:else}
								<Eye class="h-3.5 w-3.5" />
							{/if}
						</button>
					</div>
				</div>
			</div>
		</div>
	</div>

	<!-- Endpoints Reference List -->
	{#each apis as group}
		<div class="rounded-lg border border-border bg-card p-5">
			<div class="mb-4">
				<h2 class="text-sm font-semibold text-foreground">{group.title}</h2>
				<p class="text-xs text-muted-foreground mt-0.5">{group.description}</p>
			</div>

			<div class="space-y-4">
				{#each group.endpoints as ep, idx}
					{@const id = `${group.title}-${idx}`}
					<div class="rounded-lg border border-border bg-background/50 p-4 transition-colors hover:border-border/80">
						<div class="flex flex-wrap items-center justify-between gap-3 mb-2">
							<div class="flex items-center gap-2.5">
								<span class="text-[10px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded font-mono">{ep.method}</span>
								<span class="text-xs font-mono font-semibold text-foreground">{ep.path}</span>
							</div>
							<span class="text-[10px] text-muted-foreground">{ep.desc}</span>
						</div>

						<!-- Copyable Curl Codeblock -->
						<div class="relative bg-zinc-950 rounded-md border border-white/5 p-3 flex items-center justify-between font-mono text-[10px] text-zinc-300">
							<div class="flex items-center gap-2 overflow-x-auto select-all pr-10 whitespace-nowrap scrollbar-none">
								<Terminal class="h-3.5 w-3.5 text-zinc-500 shrink-0" />
								<span>{ep.curl}</span>
							</div>
							
							<button
								onclick={() => copyToClipboard(ep.curl, id)}
								class="absolute right-2.5 top-1/2 -translate-y-1/2 p-1.5 rounded bg-zinc-900 border border-white/5 text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
								title="Copy to clipboard"
							>
								{#if copiedId === id}
									<span in:fade={{ duration: 150 }} class="text-green-500">
										<Check class="h-3.5 w-3.5" />
									</span>
								{:else}
									<Copy class="h-3.5 w-3.5" />
								{/if}
							</button>
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/each}
</div>

<style>
	/* Hide scrollbar for code snippet paths */
	.scrollbar-none::-webkit-scrollbar {
		display: none;
	}
	.scrollbar-none {
		-ms-overflow-style: none;
		scrollbar-width: none;
	}
</style>
