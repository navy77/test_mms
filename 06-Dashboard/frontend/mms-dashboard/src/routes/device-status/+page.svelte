<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { API_URLS } from '$lib/config';
	import { Wifi, WifiOff, LayoutGrid, Server, RefreshCw } from 'lucide-svelte';

	let selectedProcess = $state('demo1');
	let devices: any[] = $state([]);
	let loading = $state(false);
	let lastUpdated = $state('');

	async function loadDevices() {
		loading = true;
		try {
			// Query current online/offline status from ClickHouse device_tb
			const res = await fetch(`${API_URLS.rest}/api/v1/device/currently/${selectedProcess}`);
			if (res.ok) {
				devices = await res.json();
			} else {
				throw new Error('API Error');
			}
		} catch (error) {
			console.warn('Failed to load device connectivity, using mock data:', error);
			generateFallbackData();
		} finally {
			loading = false;
			lastUpdated = new Date().toLocaleTimeString();
		}
	}

	function generateFallbackData() {
		// Mock registered devices with process, device, and connectivity status
		devices = [
			{ device: 'no_850', process: 'demo1', status: 'online', mac_id: 'mac-a1', modbus: 1, broker: 1 },
			{ device: 'no_851', process: 'demo1', status: 'online', mac_id: 'mac-a2', modbus: 1, broker: 1 },
			{ device: 'no_852', process: 'demo1', status: 'online', mac_id: 'mac-a3', modbus: 1, broker: 1 },
			{ device: 'no_853', process: 'demo1', status: 'online', mac_id: 'mac-a4', modbus: 1, broker: 1 },
			{ device: 'no_854', process: 'demo1', status: 'offline', mac_id: 'mac-a5', modbus: 1, broker: 1 },
			{ device: 'no_855', process: 'demo1', status: 'online', mac_id: 'mac-a6', modbus: 1, broker: 1 },
			{ device: 'no_856', process: 'demo1', status: 'online', mac_id: 'mac-a7', modbus: 1, broker: 1 },
			{ device: 'no_857', process: 'demo1', status: 'online', mac_id: 'mac-a8', modbus: 1, broker: 1 }
		];
	}

	onMount(async () => {
		await loadDevices();
	});

	$effect(() => {
		loadDevices();
	});
</script>

<div class="space-y-6">
	<!-- Top Option Bar -->
	<div class="rounded-2xl border border-[#1f242f] bg-[#0d1117] p-5 shadow-lg flex flex-wrap items-center justify-between gap-4">
		<div class="flex items-center gap-3">
			<Server class="h-6 w-6 text-indigo-500" />
			<div>
				<h2 class="text-base font-bold text-white">Device Connectivity Status</h2>
				<p class="text-xs text-gray-400">Monitor active communication logs and MQTT broker bindings</p>
			</div>
		</div>

		<div class="flex items-center gap-4 flex-wrap">
			<!-- Refresh Indicator -->
			<div class="text-xs text-gray-500 flex items-center gap-1">
				<span>Last update: {lastUpdated}</span>
				<button onclick={loadDevices} class="p-1 hover:text-indigo-400 transition-colors" title="Force Refresh">
					<RefreshCw class="h-3.5 w-3.5 {loading ? 'animate-spin' : ''}" />
				</button>
			</div>

			<!-- Selector -->
			<div class="flex items-center gap-2 bg-[#161b22] border border-[#1f242f] rounded-lg px-3 py-2">
				<LayoutGrid class="h-4 w-4 text-gray-400" />
				<select bind:value={selectedProcess} class="bg-transparent text-sm text-gray-200 outline-none cursor-pointer border-none p-0 focus:ring-0">
					<option value="demo1" class="bg-[#161b22]">Process: Demo 1</option>
					<option value="demo2" class="bg-[#161b22]">Process: Demo 2</option>
				</select>
			</div>
		</div>
	</div>

	<!-- Device Cards Grid -->
	<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
		{#each devices as device}
			{@const isOnline = device.status === 'online'}
			<div 
				class="rounded-2xl border border-[#1f242f] bg-[#0d1117] p-6 shadow-md flex flex-col justify-between hover:border-[#2f384a] transition-all relative overflow-hidden"
			>
				<!-- Side Glow bar based on status -->
				<div class="absolute left-0 top-0 bottom-0 w-1.5 {isOnline ? 'bg-green-500' : 'bg-rose-500'}"></div>
				
				<div class="flex justify-between items-start pl-2">
					<div class="space-y-1">
						<span class="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Device ID</span>
						<h3 class="text-lg font-bold text-white tracking-wide">{device.device}</h3>
					</div>
					
					<div 
						class="rounded-lg p-2 border 
						{isOnline 
							? 'bg-green-500/10 text-green-400 border-green-500/20' 
							: 'bg-rose-500/10 text-rose-400 border-rose-500/20'}"
					>
						{#if isOnline}
							<Wifi class="h-5 w-5" />
						{:else}
							<WifiOff class="h-5 w-5 animate-pulse" />
						{/if}
					</div>
				</div>

				<!-- Stats list -->
				<div class="mt-6 space-y-2 pl-2 text-xs text-gray-400">
					<div class="flex justify-between">
						<span>MAC ID:</span>
						<span class="font-mono text-white">{device.mac_id || 'mac-unknown'}</span>
					</div>
					<div class="flex justify-between">
						<span>Modbus Binding:</span>
						<span class="text-white">{device.modbus === 1 ? 'Enabled (ID 1)' : 'Disabled'}</span>
					</div>
					<div class="flex justify-between">
						<span>Broker Port:</span>
						<span class="text-white">Active</span>
					</div>
				</div>

				<!-- Status Badge -->
				<div class="mt-4 pt-4 border-t border-[#1f242f] flex justify-end pl-2">
					<span 
						class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider border
						{isOnline 
							? 'bg-green-500/10 text-green-400 border-green-500/20' 
							: 'bg-rose-500/10 text-rose-400 border-rose-500/20'}"
					>
						{#if isOnline}
							<span class="h-1.5 w-1.5 rounded-full bg-green-500"></span>
							<span>Online</span>
						{:else}
							<span class="h-1.5 w-1.5 rounded-full bg-rose-500 animate-ping"></span>
							<span>Offline</span>
						{/if}
					</span>
				</div>
			</div>
		{/each}
	</div>
</div>
