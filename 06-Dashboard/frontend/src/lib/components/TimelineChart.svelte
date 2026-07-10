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
	let chartInstance = $state<any>(null);
	let echartsLib = $state<any>(null);

	let segments = $state<any[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let pollInterval: any = null;

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

	async function fetchTimelineData(p: string, d: string) {
		if (!p || !d) return;
		loading = segments.length === 0;
		error = null;
		try {
			const apiHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
			const res = await fetch(`http://${apiHost}:8003/api/v1/status/state/${p}/${d}`);
			if (!res.ok) {
				throw new Error(`Failed to fetch timeline data (${res.status})`);
			}
			const json = await res.json();
			if (json && Array.isArray(json.data)) {
				segments = json.data;
				error = null;
			}
		} catch (err: any) {
			console.error('Error fetching timeline data:', err);
			if (segments.length === 0) {
				error = err.message || 'Failed to load timeline';
			}
		} finally {
			loading = false;
		}
	}

	// Trigger REST API fetching and polling when process or device changes
	$effect(() => {
		if (process && device) {
			fetchTimelineData(process, device);
			if (pollInterval) clearInterval(pollInterval);
			pollInterval = setInterval(() => {
				fetchTimelineData(process, device);
			}, 30000); // Poll every 10 seconds
		}
		return () => {
			if (pollInterval) {
				clearInterval(pollInterval);
				pollInterval = null;
			}
		};
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

	// 1. Initialize ECharts instance ONCE when the element and library are ready
	$effect(() => {
		if (!chartEl || !echartsLib) return;

		chartInstance = echartsLib.init(chartEl);

		return () => {
			if (chartInstance) {
				chartInstance.dispose();
				chartInstance = null;
			}
		};
	});

	// 2. Dynamically update ECharts options in-place when segments change
	$effect(() => {
		if (!chartInstance || segments.length === 0) return;

		const range = getProductionRange();

		const data = segments.map((seg) => {
			const startTime = new Date(seg.start_time).getTime();
			const endTime = new Date(seg.end_time).getTime();
			return {
				name: seg.status,
				value: [0, startTime, endTime, seg.status],
				itemStyle: {
					color: colorMap[seg.status] || '#EBECEF'
				}
			};
		});

		const options = {
			animation: false,
			backgroundColor: 'transparent',
			grid: {
				top: 4,
				right: 12,
				bottom: 24,
				left: 12,
				containLabel: false
			},
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

					const start = new Date(startMs).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
					const end = new Date(endMs).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
					const durationSec = Math.round((endMs - startMs) / 1000);
					const durationMin = Math.round(durationSec / 60 * 10) / 10;

					return `
						<div style="font-family: sans-serif; line-height: 1.4; padding: 6px 10px; background-color: rgba(15, 23, 42, 0.95); border: 1px solid rgba(51, 65, 85, 0.5); border-radius: 6px; color: #f8fafc; font-size: 11px; min-w: 120px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);">
							<div style="font-weight: 600; text-transform: capitalize; display: flex; align-items: center; gap: 6px; margin-bottom: 2px;">
								<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: ${color}; shrink: 0;"></span>
								Status: ${status}
							</div>
							<div>Duration: ${durationMin}m (${durationSec}s)</div>
							<div style="color: #94a3b8; font-size: 9px;">${start} - ${end}</div>
						</div>
					`;
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
					formatter: function (value: number) {
						const d = new Date(value);
						const hh = String(d.getHours()).padStart(2, '0');
						const mm = String(d.getMinutes()).padStart(2, '0');
						return `${hh}:${mm}`;
					}
				}
			},
			yAxis: {
				type: 'category',
				data: ['Timeline'],
				show: false
			},
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
								height: height
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
					encode: {
						x: [1, 2],
						y: 0
					},
					data: data
				}
			]
		};

		chartInstance.setOption(options);
	});

	onDestroy(() => {
		if (pollInterval) {
			clearInterval(pollInterval);
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
