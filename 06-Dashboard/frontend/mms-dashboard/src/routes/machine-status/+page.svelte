<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { API_URLS } from '$lib/config';
	import { Cpu, LayoutGrid, Clock, ListCollapse } from 'lucide-svelte';
	import * as echarts from 'echarts';

	let selectedProcess = $state('demo1');
	let statusData: any[] = $state([]);
	let chartDom: HTMLDivElement | null = $state(null);
	let myChart: echarts.ECharts | null = null;
	let loading = $state(false);

	async function loadStatus() {
		loading = true;
		try {
			// Fetch machine status currently from clickhouse status_tb
			const res = await fetch(`${API_URLS.rest}/api/v1/status/currently/${selectedProcess}`);
			if (res.ok) {
				statusData = await res.json();
			} else {
				throw new Error('API Error');
			}
		} catch (error) {
			console.warn('Failed to load machine status, using fallbacks:', error);
			generateFallbackData();
		} finally {
			loading = false;
			updateChart();
		}
	}

	function generateFallbackData() {
		// Mock machine status logs representing states and durations
		statusData = [
			{ device: 'Machine A (no_1)', status: 'running', duration: 18000, start_time: '07:00:00', end_time: '12:00:00' },
			{ device: 'Machine A (no_1)', status: 'idle', duration: 3600, start_time: '12:00:00', end_time: '13:00:00' },
			{ device: 'Machine A (no_1)', status: 'running', duration: 7200, start_time: '13:00:00', end_time: '15:00:00' },
			{ device: 'Machine B (no_2)', status: 'running', duration: 25200, start_time: '07:00:00', end_time: '14:00:00' },
			{ device: 'Machine B (no_2)', status: 'offline', duration: 3600, start_time: '14:00:00', end_time: '15:00:00' },
			{ device: 'Machine C (no_3)', status: 'offline', duration: 28800, start_time: '07:00:00', end_time: '15:00:00' }
		];
	}

	function updateChart() {
		if (!myChart) return;

		// Calculate total duration for each status group
		const totals: Record<string, number> = { running: 0, idle: 0, offline: 0 };
		statusData.forEach(row => {
			const status = row.status?.toLowerCase();
			if (status in totals) {
				totals[status] += row.duration || 0;
			}
		});

		const chartData = [
			{ value: totals.running / 60, name: 'Running', itemStyle: { color: '#22c55e' } },
			{ value: totals.idle / 60, name: 'Idle', itemStyle: { color: '#eab308' } },
			{ value: totals.offline / 60, name: 'Offline', itemStyle: { color: '#ef4444' } }
		];

		const option = {
			backgroundColor: 'transparent',
			tooltip: {
				trigger: 'item',
				formatter: '{b}: {c} mins ({d}%)'
			},
			legend: {
				bottom: '0%',
				left: 'center',
				textStyle: { color: '#8a92a6' }
			},
			series: [
				{
					name: 'Time Distribution',
					type: 'pie',
					radius: ['45%', '70%'],
					avoidLabelOverlap: false,
					itemStyle: {
						borderRadius: 8,
						borderColor: '#0d1117',
						borderWidth: 2
					},
					label: {
						show: false,
						position: 'center'
					},
					emphasis: {
						label: {
							show: true,
							fontSize: 16,
							fontWeight: 'bold',
							color: '#ffffff'
						}
					},
					labelLine: {
						show: false
					},
					data: chartData
				}
			]
		};

		myChart.setOption(option);
	}

	// Format duration into readable hours/minutes
	function formatDuration(sec: number) {
		const hrs = Math.floor(sec / 3600);
		const mins = Math.floor((sec % 3600) / 60);
		if (hrs > 0) {
			return `${hrs}h ${mins}m`;
		}
		return `${mins}m`;
	}

	onMount(async () => {
		if (chartDom) {
			myChart = echarts.init(chartDom, 'dark');
		}
		await loadStatus();

		const handleResize = () => myChart?.resize();
		window.addEventListener('resize', handleResize);
	});

	onDestroy(() => {
		if (myChart) {
			myChart.dispose();
		}
	});

	$effect(() => {
		loadStatus();
	});
</script>

<div class="space-y-6">
	<!-- Top Options bar -->
	<div class="rounded-2xl border border-[#1f242f] bg-[#0d1117] p-5 shadow-lg flex flex-wrap items-center justify-between gap-4">
		<div class="flex items-center gap-3">
			<Cpu class="h-6 w-6 text-indigo-500" />
			<div>
				<h2 class="text-base font-bold text-white">Machine Status & OEE</h2>
				<p class="text-xs text-gray-400">Track runtime, idle state, and downtime logs</p>
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

	<!-- Status Distribution & Timelines -->
	<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
		<!-- Pie Chart Distribution -->
		<div class="rounded-2xl border border-[#1f242f] bg-[#0d1117] p-6 shadow-xl space-y-4 flex flex-col justify-between">
			<div>
				<h3 class="text-sm font-bold text-white uppercase tracking-wider">State Distribution</h3>
				<p class="text-xs text-gray-400 mt-1">Ratio of active running time against downtime.</p>
			</div>
			
			<div bind:this={chartDom} class="h-[280px] w-full"></div>
			<div class="h-4"></div>
		</div>

		<!-- Status Log Table -->
		<div class="rounded-2xl border border-[#1f242f] bg-[#0d1117] p-6 shadow-xl lg:col-span-2 space-y-4 flex flex-col justify-between">
			<div class="space-y-4">
				<div class="flex items-center gap-2 text-white">
					<ListCollapse class="h-5 w-5 text-indigo-500" />
					<h3 class="text-sm font-bold uppercase tracking-wider">Status Logs</h3>
				</div>

				<div class="overflow-x-auto max-h-[300px]">
					<table class="w-full text-left text-xs border-collapse">
						<thead>
							<tr class="border-b border-[#1f242f] text-gray-400 font-semibold">
								<th class="py-2.5">Device Name</th>
								<th class="py-2.5">Current State</th>
								<th class="py-2.5"><span class="flex items-center gap-1"><Clock class="h-3.5 w-3.5" /> Start Time</span></th>
								<th class="py-2.5">End Time</th>
								<th class="py-2.5 text-right">Duration</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-[#1f242f]/50 text-gray-300">
							{#each statusData as row}
								<tr class="hover:bg-[#161b22]/30 transition-colors">
									<td class="py-2.5 font-semibold text-white">{row.device}</td>
									<td class="py-2.5">
										<span 
											class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase border
											{row.status === 'running' ? 'bg-green-500/10 text-green-400 border-green-500/20' : 
											 row.status === 'idle' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' : 
											 'bg-rose-500/10 text-rose-400 border-rose-500/20'}"
										>
											{row.status}
										</span>
									</td>
									<td class="py-2.5">{row.start_time}</td>
									<td class="py-2.5">{row.end_time || '-'}</td>
									<td class="py-2.5 text-right font-mono font-semibold text-white">{formatDuration(row.duration)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>

			<!-- Total Runtime Summary -->
			<div class="mt-4 pt-4 border-t border-[#1f242f] flex justify-between items-center text-xs text-gray-400">
				<span>Monitored Duration Summary:</span>
				<span class="text-sm font-bold text-white">
					Active Running: {formatDuration(statusData.filter(r => r.status === 'running').reduce((sum, r) => sum + (r.duration || 0), 0))}
				</span>
			</div>
		</div>
	</div>
</div>
