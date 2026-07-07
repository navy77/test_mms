<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { API_URLS } from '$lib/config';
	import { TrendingUp, BarChart3, Calendar, Layers, TableProperties } from 'lucide-svelte';
	import * as echarts from 'echarts';

	let selectedProcess = $state('demo1');
	let selectedTimeframe = $state('hourly'); // hourly | daily | monthly
	let productionRows: any[] = $state([]);
	let chartDom: HTMLDivElement | null = $state(null);
	let myChart: echarts.ECharts | null = null;
	let loading = $state(false);

	// Load production data based on process and timeframe
	async function loadProductionData() {
		loading = true;
		try {
			let url = '';
			if (selectedTimeframe === 'hourly') {
				url = `${API_URLS.rest}/api/v1/data/hourly/${selectedProcess}`;
			} else if (selectedTimeframe === 'daily') {
				url = `${API_URLS.rest}/api/v1/data/daily/${selectedProcess}`;
			} else {
				// Monthly (current year and month)
				const now = new Date();
				url = `${API_URLS.rest}/api/v1/data/monthly/${now.getFullYear()}/${now.getMonth() + 1}/${selectedProcess}`;
			}

			const res = await fetch(url);
			if (res.ok) {
				const data = await res.json();
				// The endpoint formats are Pydantic responses containing lists
				productionRows = data || [];
			} else {
				throw new Error('API returned error status');
			}
		} catch (error) {
			console.warn('Failed to load production from API, using fallbacks:', error);
			generateFallbackData();
		} finally {
			loading = false;
			updateChart();
		}
	}

	function generateFallbackData() {
		if (selectedTimeframe === 'hourly') {
			productionRows = [
				{ time: '07:00', device: 'no_1', data1: 120, data2: 50, data3: 8 },
				{ time: '08:00', device: 'no_1', data1: 140, data2: 60, data3: 9 },
				{ time: '09:00', device: 'no_1', data1: 190, data2: 80, data3: 12 },
				{ time: '10:00', device: 'no_1', data1: 210, data2: 90, data3: 15 },
				{ time: '11:00', device: 'no_1', data1: 180, data2: 75, data3: 11 },
				{ time: '12:00', device: 'no_1', data1: 90,  data2: 40, data3: 5  },
				{ time: '13:00', device: 'no_1', data1: 230, data2: 95, data3: 18 }
			];
		} else if (selectedTimeframe === 'daily') {
			productionRows = [
				{ date: '07-01', device: 'no_1', data1: 1200, data2: 500, data3: 80 },
				{ date: '07-02', device: 'no_1', data1: 1350, data2: 580, data3: 92 },
				{ date: '07-03', device: 'no_1', data1: 1410, data2: 610, data3: 104 },
				{ date: '07-04', device: 'no_1', data1: 890,  data2: 390, data3: 50 },
				{ date: '07-05', device: 'no_1', data1: 950,  data2: 410, data3: 55 },
				{ date: '07-06', device: 'no_1', data1: 1520, data2: 680, data3: 120 },
				{ date: '07-07', device: 'no_1', data1: 1680, data2: 720, data3: 135 }
			];
		} else {
			productionRows = [
				{ month: 'Jan', device: 'no_1', data1: 32000, data2: 12000, data3: 2100 },
				{ month: 'Feb', device: 'no_1', data1: 29000, data2: 11000, data3: 1900 },
				{ month: 'Mar', device: 'no_1', data1: 35000, data2: 14000, data3: 2400 },
				{ month: 'Apr', device: 'no_1', data1: 38000, data2: 15500, data3: 2700 },
				{ month: 'May', device: 'no_1', data1: 41000, data2: 17000, data3: 2900 },
				{ month: 'Jun', device: 'no_1', data1: 44000, data2: 18500, data3: 3100 }
			];
		}
	}

	function updateChart() {
		if (!myChart) return;

		const labels = productionRows.map(row => row.time || row.date || row.month || 'N/A');
		const data1Values = productionRows.map(row => row.data1 || 0);
		const data2Values = productionRows.map(row => row.data2 || 0);

		const option = {
			backgroundColor: 'transparent',
			tooltip: {
				trigger: 'axis',
				axisPointer: { type: 'shadow' }
			},
			legend: {
				data: ['Total Output (Data 1)', 'Defects / Scrap (Data 2)'],
				textStyle: { color: '#8a92a6' },
				top: '5%'
			},
			grid: {
				top: '20%',
				left: '3%',
				right: '4%',
				bottom: '3%',
				containLabel: true
			},
			xAxis: {
				type: 'category',
				data: labels,
				axisLine: { lineStyle: { color: '#2c313d' } },
				axisLabel: { color: '#8a92a6' }
			},
			yAxis: {
				type: 'value',
				splitLine: { lineStyle: { color: '#1f242f' } },
				axisLabel: { color: '#8a92a6' }
			},
			series: [
				{
					name: 'Total Output (Data 1)',
					type: 'bar',
					data: data1Values,
					itemStyle: {
						color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
							{ offset: 0, color: '#3b82f6' },
							{ offset: 1, color: '#1d4ed8' }
						]),
						borderRadius: [4, 4, 0, 0]
					}
				},
				{
					name: 'Defects / Scrap (Data 2)',
					type: 'bar',
					data: data2Values,
					itemStyle: {
						color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
							{ offset: 0, color: '#ef4444' },
							{ offset: 1, color: '#b91c1c' }
						]),
						borderRadius: [4, 4, 0, 0]
					}
				}
			]
		};

		myChart.setOption(option);
	}

	onMount(async () => {
		if (chartDom) {
			myChart = echarts.init(chartDom, 'dark');
		}
		await loadProductionData();

		const handleResize = () => myChart?.resize();
		window.addEventListener('resize', handleResize);
	});

	onDestroy(() => {
		if (myChart) {
			myChart.dispose();
		}
	});

	// Trigger reload on selection change
	$effect(() => {
		loadProductionData();
	});
</script>

<div class="space-y-6">
	<!-- Control Panel -->
	<div class="rounded-2xl border border-[#1f242f] bg-[#0d1117] p-5 shadow-lg flex flex-wrap items-center justify-between gap-4">
		<div class="flex items-center gap-3">
			<TrendingUp class="h-6 w-6 text-indigo-500" />
			<div>
				<h2 class="text-base font-bold text-white">Production Analytics</h2>
				<p class="text-xs text-gray-400">View real-time OEE output and counts</p>
			</div>
		</div>

		<div class="flex items-center gap-3 flex-wrap">
			<!-- Process Selector -->
			<div class="flex items-center gap-2 bg-[#161b22] border border-[#1f242f] rounded-lg px-3 py-2">
				<Layers class="h-4 w-4 text-gray-400" />
				<select bind:value={selectedProcess} class="bg-transparent text-sm text-gray-200 outline-none cursor-pointer border-none p-0 focus:ring-0">
					<option value="demo1" class="bg-[#161b22]">Process: Demo 1</option>
					<option value="demo2" class="bg-[#161b22]">Process: Demo 2</option>
				</select>
			</div>

			<!-- Timeframe Select Toggle -->
			<div class="flex rounded-lg bg-[#161b22] p-1 border border-[#1f242f]">
				<button 
					onclick={() => selectedTimeframe = 'hourly'}
					class="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-md transition-colors
					{selectedTimeframe === 'hourly' ? 'bg-indigo-600 text-white shadow-md' : 'text-gray-400 hover:text-gray-200'}"
				>
					<BarChart3 class="h-3.5 w-3.5" />
					<span>Hourly</span>
				</button>
				<button 
					onclick={() => selectedTimeframe = 'daily'}
					class="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-md transition-colors
					{selectedTimeframe === 'daily' ? 'bg-indigo-600 text-white shadow-md' : 'text-gray-400 hover:text-gray-200'}"
				>
					<Calendar class="h-3.5 w-3.5" />
					<span>Daily</span>
				</button>
				<button 
					onclick={() => selectedTimeframe = 'monthly'}
					class="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-md transition-colors
					{selectedTimeframe === 'monthly' ? 'bg-indigo-600 text-white shadow-md' : 'text-gray-400 hover:text-gray-200'}"
				>
					<Calendar class="h-3.5 w-3.5" />
					<span>Monthly</span>
				</button>
			</div>
		</div>
	</div>

	<!-- Chart & Detailed Output -->
	<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
		<!-- EChart Output Trends -->
		<div class="rounded-2xl border border-[#1f242f] bg-[#0d1117] p-6 shadow-xl lg:col-span-2 space-y-4">
			<h3 class="text-sm font-bold text-white uppercase tracking-wider">Output Trend Graph</h3>
			<div bind:this={chartDom} class="h-[360px] w-full"></div>
		</div>

		<!-- Table Detail Summary -->
		<div class="rounded-2xl border border-[#1f242f] bg-[#0d1117] p-6 shadow-xl flex flex-col justify-between">
			<div class="space-y-4">
				<div class="flex items-center gap-2 text-white">
					<TableProperties class="h-5 w-5 text-indigo-500" />
					<h3 class="text-sm font-bold uppercase tracking-wider">Production Logs</h3>
				</div>

				<div class="overflow-x-auto max-h-[300px]">
					<table class="w-full text-left text-xs border-collapse">
						<thead>
							<tr class="border-b border-[#1f242f] text-gray-400 font-semibold">
								<th class="py-2.5">Timeframe</th>
								<th class="py-2.5">Device</th>
								<th class="py-2.5 text-right">Output</th>
								<th class="py-2.5 text-right text-rose-400">Scrap</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-[#1f242f]/50 text-gray-300">
							{#each productionRows as row}
								<tr class="hover:bg-[#161b22]/30 transition-colors">
									<td class="py-2.5">{row.time || row.date || row.month || 'N/A'}</td>
									<td class="py-2.5">{row.device || 'N/A'}</td>
									<td class="py-2.5 text-right font-semibold text-white">{row.data1?.toLocaleString() || 0}</td>
									<td class="py-2.5 text-right text-rose-400">{(row.data2 || 0).toLocaleString()}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>

			<!-- Totals Indicator -->
			<div class="mt-4 pt-4 border-t border-[#1f242f] flex justify-between items-center text-xs text-gray-400">
				<span>Total Processed Volume:</span>
				<span class="text-sm font-bold text-white">
					{productionRows.reduce((sum, r) => sum + (r.data1 || 0), 0).toLocaleString()} pcs
				</span>
			</div>
		</div>
	</div>
</div>
