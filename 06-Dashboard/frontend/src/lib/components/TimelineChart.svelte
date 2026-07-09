<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { LoaderCircle, AlertCircle } from 'lucide-svelte';

	interface Props {
		process: string;
		device: string;
		colorMap: Record<string, string>;
	}

	let { process, device, colorMap }: Props = $props();

	let chartEl = $state<HTMLElement | null>(null);
	let chartInstance: any = null;
	let ApexChartsClass = $state<any>(null);

	let segments = $state<any[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let sse: EventSource | null = null;

	function connectSSE(p: string, d: string) {
		loading = true;
		error = null;
		segments = [];

		if (sse) {
			sse.close();
		}

		const url = `http://localhost:8003/api/v1/status/stream/state/${p}/${d}`;
		sse = new EventSource(url);

		sse.onmessage = (event) => {
			try {
				const payload = JSON.parse(event.data);
				if (payload && Array.isArray(payload.data)) {
					segments = payload.data;
					loading = false;
				}
			} catch (err) {
				console.error('Error parsing SSE data:', err);
			}
		};

		sse.onerror = (err) => {
			console.error('SSE connection error:', err);
			error = 'Connection lost. Retrying...';
			loading = false;
		};
	}

	// Trigger SSE connection when process or device changes
	$effect(() => {
		if (process && device) {
			connectSSE(process, device);
		}
	});

	function getProductionRange() {
		const now = new Date();
		const start = new Date(now);
		if (now.getHours() < 7) {
			start.setDate(now.getDate() - 1);
		}
		start.setHours(7, 0, 0, 0);

		const end = new Date(start);
		end.setDate(start.getDate() + 1);
		end.setHours(7, 0, 0, 0);

		return {
			min: start.getTime(),
			max: end.getTime()
		};
	}

	// Dynamically import ApexCharts on client side
	onMount(async () => {
		const module = await import('apexcharts');
		ApexChartsClass = module.default;
	});

	// Render/update ApexCharts when segments or ApexChartsClass is ready
	$effect(() => {
		if (chartEl && ApexChartsClass && segments.length > 0) {
			const range = getProductionRange();
			const options = {
				chart: {
					type: 'rangeBar',
					height: 100,
					toolbar: { show: false },
					animations: { enabled: false },
					zoom: {
						enabled: false
					}
				},
				plotOptions: {
					bar: {
						horizontal: true,
						barHeight: '100%',
						rangeBarGroupRows: true
					}
				},
				series: [
					{
						name: 'State',
						data: segments.map(seg => ({
							x: 'Timeline',
							y: [
								new Date(seg.start_time).getTime(),
								new Date(seg.end_time).getTime()
							],
							fillColor: colorMap[seg.status] || '#EBECEF',
							status: seg.status
						}))
					}
				],
				xaxis: {
					type: 'datetime',
					min: range.min,
					max: range.max,
					labels: {
						datetimeUTC: false,
						format: 'HH:mm',
						style: { colors: '#9ca3af', fontSize: '10px' }
					},
					axisBorder: { show: false },
					axisTicks: { show: false }
				},
				yaxis: {
					show: false
				},
				grid: {
					show: false,
					padding: { top: 0, right: 10, bottom: 0, left: 10 }
				},
				tooltip: {
					custom: function({ series, seriesIndex, dataPointIndex, w }: any) {
						const data = w.config.series[seriesIndex].data[dataPointIndex];
						const start = new Date(data.y[0]).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
						const end = new Date(data.y[1]).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
						const durationSec = Math.round((data.y[1] - data.y[0]) / 1000);
						const durationMin = Math.round(durationSec / 60 * 10) / 10;
						
						return `
							<div class="px-2.5 py-1.5 bg-popover text-popover-foreground rounded-md border border-border shadow-md text-xs space-y-0.5">
								<div class="font-semibold capitalize flex items-center gap-1.5">
									<span class="w-2 h-2 rounded-full" style="background-color: ${colorMap[data.status] || '#9ca3af'}"></span>
									Status: ${data.status}
								</div>
								<div>Duration: ${durationMin}m (${durationSec}s)</div>
								<div class="text-muted-foreground text-[10px]">${start} - ${end}</div>
							</div>
						`;
					}
				}
			};

			if (chartInstance) {
				chartInstance.destroy();
			}
			chartInstance = new ApexChartsClass(chartEl, options);
			chartInstance.render();
		}
	});

	onDestroy(() => {
		if (sse) sse.close();
		if (chartInstance) chartInstance.destroy();
	});
</script>

<div class="w-full min-h-[90px] relative">
	{#if loading && segments.length === 0}
		<div class="absolute inset-0 flex items-center justify-center bg-background/50 z-10">
			<LoaderCircle class="h-5 w-5 animate-spin text-muted-foreground" />
		</div>
	{/if}
	{#if error && segments.length === 0}
		<div class="absolute inset-0 flex items-center gap-2 text-destructive justify-center text-sm bg-background/50 z-10">
			<AlertCircle class="h-4 w-4" />
			<span>{error}</span>
		</div>
	{/if}
	<div bind:this={chartEl} class="w-full h-[90px]"></div>
</div>
