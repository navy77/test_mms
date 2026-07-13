<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { LoaderCircle, AlertCircle } from 'lucide-svelte';

	interface StatusSegment {
		status: string;
		duration: number;
		ratio: number;
	}

	interface DailyRecord {
		date: string;
		device: string;
		data: StatusSegment[];
		utilize: number;
	}

	interface Props {
		process: string;
		device: string;
		colorMap: Record<string, string>;
		records: DailyRecord[];
		loading: boolean;
		error: string | null;
	}

	let { process, device, colorMap, records = [], loading = true, error = null }: Props = $props();

	let chartEl = $state<HTMLElement | null>(null);
	// ECharts owns this mutable instance; it must not be reactive state.
	let chartInstance: any = null;
	let echartsLib = $state<any>(null);

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

	// 2. Dynamically update ECharts options in-place when records or colorMap changes
	$effect(() => {
		// Track the lazy-loaded library as a dependency.  Without this, this
		// effect can run before the instance is initialized and never run again.
		if (!echartsLib || !chartInstance) return;

		if (records.length === 0) {
			chartInstance.setOption(
				{
					animation: false,
					backgroundColor: 'transparent',
					grid: { top: 8, right: 8, bottom: 20, left: 36, containLabel: false },
					xAxis: {
						type: 'category',
						data: [],
						axisLine: { show: false },
						axisTick: { show: false },
						axisLabel: { show: false }
					},
					yAxis: {
						type: 'value',
						min: 0,
						max: 100,
						axisLabel: { show: false },
						splitLine: { show: false }
					},
					series: []
				},
				true
			);
			return;
		}

		// All unique statuses — include 'no data' so full bar is shown on empty days
		const priorityOrder = ['run', 'alarm', 'wait', 'stop', 'other', 'offline', 'no data'];
		const rawStatuses = Array.from(
			new Set(records.flatMap((d) => d.data.map((s) => s.status)))
		);
		const allStatuses = [
			...priorityOrder.filter((s) => rawStatuses.includes(s) || s === 'no data'),
			...rawStatuses.filter((s) => !priorityOrder.includes(s))
		];

		// Date labels (Day of Month)
		const categories = records.map((r) => {
			const d = new Date(r.date + 'T00:00:00');
			return d.getDate().toString();
		});

		// Stacked bar series — ratio is already in % (e.g. 82.9 = 82.9%)
		const barSeries = allStatuses.map((status) => ({
			name: status === 'no data' ? 'No Data' : status.charAt(0).toUpperCase() + status.slice(1),
			type: 'bar',
			stack: 'status', // Same stack ID to stack bars
			color: colorMap[status] || '#374151',
			barWidth: '80%',
			data: records.map((r) => {
				const seg = r.data.find((s) => s.status === status);
				return seg ? Math.round(seg.ratio * 10) / 10 : 0;
			})
		}));

		// Utilize % line — utilize is already in % (e.g. 29.9 = 29.9%)
		const lineSeries = {
			name: 'Utilize %',
			type: 'line',
			color: '#16537e',
			symbol: 'circle',
			symbolSize: 5,
			showSymbol: false,
			lineStyle: {
				width: 2,
				color: '#16537e'
			},
			data: records.map((r) => Math.round(r.utilize * 10) / 10)
		};

		const series = [...barSeries, lineSeries];

		// 3. ECharts options configuration
		const options = {
			animation: false,
			backgroundColor: 'transparent',
			grid: {
				top: 8,
				right: 8,
				bottom: 20,
				left: 36,
				containLabel: false
			},
			tooltip: {
				trigger: 'axis',
				axisPointer: {
					type: 'shadow'
				},
				backgroundColor: 'rgba(15, 23, 42, 0.95)', // slate-900 with opacity
				borderColor: 'rgba(51, 65, 85, 0.5)',     // slate-700/50
				borderWidth: 1,
				padding: [6, 10],
				textStyle: {
					color: '#f8fafc', // slate-50
					fontSize: 10,
					fontFamily: 'sans-serif'
				},
				formatter: function (params: any) {
					if (!params || params.length === 0) return '';
					const day = params[0].name;
					let html = `<div style="font-family: sans-serif; line-height: 1.4;">`;
					html += `<div style="font-weight: 600; color: #94a3b8; border-bottom: 1px solid #334155; padding-bottom: 2px; margin-bottom: 4px;">Day ${day}</div>`;
					
					// Iterate through parameters to display values
					params.forEach((p: any) => {
						const name = p.seriesName;
						const val = p.value !== undefined && p.value !== null ? p.value : 0;
						const color = p.color;
						html += `<div style="display: flex; align-items: center; justify-content: space-between; gap: 16px;">
							<div style="display: flex; align-items: center; gap: 6px;">
								<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: ${color};"></span>
								<span>${name}</span>
							</div>
							<span style="font-weight: 500;">${val}%</span>
						</div>`;
					});
					
					html += `</div>`;
					return html;
				}
			},
			xAxis: {
				type: 'category',
				data: categories,
				axisLine: { show: false },
				axisTick: { show: false },
				axisLabel: {
					color: '#6b7280',
					fontSize: 9,
					interval: 4 // Avoid overlapping labels
				}
			},
			yAxis: {
				type: 'value',
				min: 0,
				max: 100,
				splitNumber: 4,
				axisLabel: {
					color: '#6b7280',
					fontSize: 9,
					formatter: '{value}%'
				},
				splitLine: {
					lineStyle: {
						color: 'rgba(255, 255, 255, 0.05)',
						type: 'dashed'
					}
				}
			},
			series: series
		};

		chartInstance.setOption(options, true);
		chartInstance.resize();
	});

	onDestroy(() => {
		if (typeof window !== 'undefined') {
			window.removeEventListener('resize', handleResize);
		}
	});
</script>

<div class="w-full relative" style="height:150px">
	{#if loading}
		<div class="absolute inset-0 flex items-center justify-center z-10">
			<LoaderCircle class="h-4 w-4 animate-spin text-muted-foreground" />
		</div>
	{:else if error}
		<div
			class="absolute inset-0 flex items-center justify-center gap-1.5 text-muted-foreground z-10"
		>
			<AlertCircle class="h-3.5 w-3.5" />
			<span class="text-[10px]">{error}</span>
		</div>
	{/if}
	<div bind:this={chartEl} class="w-full h-full"></div>
</div>
