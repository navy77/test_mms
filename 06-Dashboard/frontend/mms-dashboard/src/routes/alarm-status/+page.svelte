<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { API_URLS } from '$lib/config';
	import { AlertTriangle, LayoutGrid, Clock, ListFilter } from 'lucide-svelte';
	import * as echarts from 'echarts';

	let selectedProcess = $state('demo1');
	let alarmData: any[] = $state([]);
	let chartDom: HTMLDivElement | null = $state(null);
	let myChart: echarts.ECharts | null = null;
	let loading = $state(false);

	async function loadAlarms() {
		loading = true;
		try {
			// Fetch alarm status currently from clickhouse alarm_tb
			const res = await fetch(`${API_URLS.rest}/api/v1/alarm/currently/${selectedProcess}`);
			if (res.ok) {
				alarmData = await res.json();
			} else {
				throw new Error('API Error');
			}
		} catch (error) {
			console.warn('Failed to load alarms, using fallbacks:', error);
			generateFallbackData();
		} finally {
			loading = false;
			updateChart();
		}
	}

	function generateFallbackData() {
		// Mock alarm data showing alarm states, durations, and counts
		alarmData = [
			{ device: 'no_1', status: 'alarm_1', duration: 1200, start_time: '08:15:00', end_time: '08:35:00', alarm_name: 'Overheating Error' },
			{ device: 'no_1', status: 'alarm_2', duration: 600, start_time: '11:45:00', end_time: '11:55:00', alarm_name: 'Low Pressure Limit' },
			{ device: 'no_2', status: 'alarm_1', duration: 2400, start_time: '10:00:00', end_time: '10:40:00', alarm_name: 'Overheating Error' },
			{ device: 'no_3', status: 'alarm_3', duration: 1800, start_time: '14:20:00', end_time: '14:50:00', alarm_name: 'Emergency Stop' }
		];
	}

	function updateChart() {
		if (!myChart) return;

		// Calculate total count by alarm name/category
		const alarmCounts: Record<string, number> = {};
		alarmData.forEach(row => {
			const name = row.alarm_name || row.status || 'Unknown';
			alarmCounts[name] = (alarmCounts[name] || 0) + 1;
		});

		const categories = Object.keys(alarmCounts);
		const values = Object.values(alarmCounts);

		const option = {
			backgroundColor: 'transparent',
			tooltip: {
				trigger: 'axis',
				axisPointer: { type: 'shadow' }
			},
			grid: {
				top: '15%',
				left: '3%',
				right: '4%',
				bottom: '3%',
				containLabel: true
			},
			xAxis: {
				type: 'value',
				splitLine: { lineStyle: { color: '#1f242f' } },
				axisLabel: { color: '#8a92a6' }
			},
			yAxis: {
				type: 'category',
				data: categories,
				axisLine: { lineStyle: { color: '#2c313d' } },
				axisLabel: { color: '#8a92a6' }
			},
			series: [
				{
					name: 'Occurrences',
					type: 'bar',
					data: values,
					itemStyle: {
						color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
							{ offset: 0, color: '#f43f5e' },
							{ offset: 1, color: '#be123c' }
						]),
						borderRadius: [0, 4, 4, 0]
					}
				}
			]
		};

		myChart.setOption(option);
	}

	function formatDuration(sec: number) {
		const mins = Math.floor(sec / 60);
		return `${mins} mins`;
	}

	onMount(async () => {
		if (chartDom) {
			myChart = echarts.init(chartDom, 'dark');
		}
		await loadAlarms();

		const handleResize = () => myChart?.resize();
		window.addEventListener('resize', handleResize);
	});

	onDestroy(() => {
		if (myChart) {
			myChart.dispose();
		}
	});

	$effect(() => {
		loadAlarms();
	});
</script>

<div class="space-y-6">
	<!-- Control Panel -->
	<div class="rounded-2xl border border-[#1f242f] bg-[#0d1117] p-5 shadow-lg flex flex-wrap items-center justify-between gap-4">
		<div class="flex items-center gap-3">
			<AlertTriangle class="h-6 w-6 text-rose-500 animate-pulse" />
			<div>
				<h2 class="text-base font-bold text-white">Alarm & Alert Status</h2>
				<p class="text-xs text-gray-400">Review frequency, logs, and triggers for active machine faults</p>
			</div>
		</div>

		<div class="flex items-center gap-2 bg-[#161b22] border border-[#1f242f] rounded-lg px-3 py-2">
			<LayoutGrid class="h-4 w-4 text-gray-400" />
			<select bind:value={selectedProcess} class="bg-transparent text-sm text-gray-200 outline-none cursor-pointer border-none p-0 focus:ring-0">
				<option value="demo1" class="bg-[#161b22]">Process: Demo 1</option>
				<option value="demo2" class="bg-[#161b22]">Process: Demo 2</option>
			</select>
		</div>
	</div>

	<!-- Chart & Alarm Log Table -->
	<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
		<!-- Alarm counts bar chart -->
		<div class="rounded-2xl border border-[#1f242f] bg-[#0d1117] p-6 shadow-xl space-y-4 flex flex-col justify-between">
			<div>
				<h3 class="text-sm font-bold text-white uppercase tracking-wider">Alarm Breakdown</h3>
				<p class="text-xs text-gray-400 mt-1">Fault occurrences classified by category.</p>
			</div>
			
			<div bind:this={chartDom} class="h-[280px] w-full"></div>
			<div class="h-4"></div>
		</div>

		<!-- Alarm Log Table -->
		<div class="rounded-2xl border border-[#1f242f] bg-[#0d1117] p-6 shadow-xl lg:col-span-2 space-y-4 flex flex-col justify-between">
			<div class="space-y-4">
				<div class="flex items-center gap-2 text-white">
					<ListFilter class="h-5 w-5 text-rose-500" />
					<h3 class="text-sm font-bold uppercase tracking-wider">Active Fault Logs</h3>
				</div>

				<div class="overflow-x-auto max-h-[300px]">
					<table class="w-full text-left text-xs border-collapse">
						<thead>
							<tr class="border-b border-[#1f242f] text-gray-400 font-semibold">
								<th class="py-2.5">Device ID</th>
								<th class="py-2.5">Alarm Name</th>
								<th class="py-2.5">Code</th>
								<th class="py-2.5"><span class="flex items-center gap-1"><Clock class="h-3.5 w-3.5" /> Start Time</span></th>
								<th class="py-2.5 text-right">Duration</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-[#1f242f]/50 text-gray-300">
							{#each alarmData as row}
								<tr class="hover:bg-[#161b22]/30 transition-colors">
									<td class="py-2.5 font-semibold text-white">{row.device}</td>
									<td class="py-2.5 text-rose-400 font-semibold">{row.alarm_name}</td>
									<td class="py-2.5 text-gray-500 uppercase font-mono">{row.status}</td>
									<td class="py-2.5">{row.start_time}</td>
									<td class="py-2.5 text-right font-mono font-semibold text-white">{formatDuration(row.duration)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>

			<!-- Summary of occurrences -->
			<div class="mt-4 pt-4 border-t border-[#1f242f] flex justify-between items-center text-xs text-gray-400">
				<span>Total Active Anomalies:</span>
				<span class="text-sm font-bold text-rose-500">
					{alarmData.length} active occurrences
				</span>
			</div>
		</div>
	</div>
</div>
