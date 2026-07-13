<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { LoaderCircle, AlertCircle } from 'lucide-svelte';

	interface Props {
		segments?: any[];
		colorMap: Record<string, string>;
		loading?: boolean;
		error?: string | null;
	}

	let { segments = [], colorMap, loading = false, error = null }: Props = $props();

	let chartEl = $state<HTMLElement | null>(null);
	let echartsLib = $state<any>(null);

	// Plain variable — NOT $state to avoid being tracked as effect dependency
	let chartInstance: any = null;

	onMount(async () => {
		echartsLib = await import('echarts');
		if (typeof window !== 'undefined') {
			window.addEventListener('resize', handleResize);
		}
	});

	function handleResize() {
		if (chartInstance) {
			chartInstance.resize();
		}
	}

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

		return { min: start.getTime(), max: end.getTime() };
	}

	// Single effect: re-runs when chartEl, echartsLib, or segments change
	$effect(() => {
		if (!chartEl || !echartsLib) return;

		// Init once
		if (!chartInstance) {
			chartInstance = echartsLib.init(chartEl);
		}

		const range = getProductionRange();

		if (segments.length === 0) {
			// Show empty time axis while waiting for data
			chartInstance.setOption({
				animation: false,
				backgroundColor: 'transparent',
				grid: { top: 4, right: 12, bottom: 24, left: 12, containLabel: false },
				xAxis: {
					type: 'time',
					min: range.min,
					max: range.max,
					axisLine: { show: false },
					axisTick: { show: false },
					splitLine: { show: false },
					axisLabel: {
						color: '#9ca3af',
						fontSize: 9,
						formatter: (value: number) => {
							const d = new Date(value);
							return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
						}
					}
				},
				yAxis: { type: 'category', data: ['Timeline'], show: false },
				series: [{ type: 'custom', renderItem: () => null, data: [] }]
			}, true);
			return;
		}

		const data = segments.map((seg) => {
			const startTime = new Date(seg.start_time).getTime();
			const endTime = new Date(seg.end_time).getTime();
			return {
				name: seg.status,
				value: [0, startTime, endTime, seg.status],
				itemStyle: { color: colorMap[seg.status] || '#EBECEF' }
			};
		});

		chartInstance.setOption(
			{
				animation: false,
				backgroundColor: 'transparent',
				grid: { top: 4, right: 12, bottom: 24, left: 12, containLabel: false },
				tooltip: {
					trigger: 'item',
					backgroundColor: 'transparent',
					borderWidth: 0,
					shadowBlur: 0,
					padding: 0,
					formatter: function (param: any) {
						const status = param.value[3];
						const startMs = param.value[1];
						const endMs = param.value[2];
						const color = param.color;
						const start = new Date(startMs).toLocaleTimeString('en-US', {
							hour12: false,
							hour: '2-digit',
							minute: '2-digit',
							second: '2-digit'
						});
						const end = new Date(endMs).toLocaleTimeString('en-US', {
							hour12: false,
							hour: '2-digit',
							minute: '2-digit',
							second: '2-digit'
						});
						const durationSec = Math.round((endMs - startMs) / 1000);
						const durationMin = Math.round((durationSec / 60) * 10) / 10;
						return `
							<div style="font-family:sans-serif;line-height:1.4;padding:6px 10px;background:rgba(15,23,42,0.95);border:1px solid rgba(51,65,85,0.5);border-radius:6px;color:#f8fafc;font-size:11px;box-shadow:0 10px 15px -3px rgba(0,0,0,.1)">
								<div style="font-weight:600;text-transform:capitalize;display:flex;align-items:center;gap:6px;margin-bottom:2px">
									<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color}"></span>
									Status: ${status}
								</div>
								<div>Duration: ${durationMin}m (${durationSec}s)</div>
								<div style="color:#94a3b8;font-size:9px">${start} – ${end}</div>
							</div>`;
					}
				},
				xAxis: {
					type: 'time',
					min: range.min,
					max: range.max,
					axisLine: { show: false },
					axisTick: { show: false },
					splitLine: { show: false },
					axisLabel: {
						color: '#9ca3af',
						fontSize: 9,
						formatter: (value: number) => {
							const d = new Date(value);
							return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
						}
					}
				},
				yAxis: { type: 'category', data: ['Timeline'], show: false },
				series: [
					{
						type: 'custom',
						renderItem: function (params: any, api: any) {
							const categoryIndex = api.value(0);
							const start = api.coord([api.value(1), categoryIndex]);
							const end = api.coord([api.value(2), categoryIndex]);
							const height = params.coordSys.height * 0.8;
							const rectShape = echartsLib.graphic.clipRectByRect(
								{
									x: start[0],
									y: start[1] - height / 2,
									width: Math.max(end[0] - start[0], 1),
									height
								},
								{
									x: params.coordSys.x,
									y: params.coordSys.y,
									width: params.coordSys.width,
									height: params.coordSys.height
								}
							);
							return (
								rectShape && {
									type: 'rect',
									transition: ['shape'],
									shape: rectShape,
									style: api.style()
								}
							);
						},
						encode: { x: [1, 2], y: 0 },
						data
					}
				]
			},
			true  // notMerge: replace series data cleanly each update
		);
	});

	onDestroy(() => {
		if (chartInstance) {
			chartInstance.dispose();
			chartInstance = null;
		}
		if (typeof window !== 'undefined') {
			window.removeEventListener('resize', handleResize);
		}
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
