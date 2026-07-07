<script lang="ts">
	import './layout.css';
	import { page } from '$app/state';
	import { 
		Home, 
		TrendingUp, 
		Cpu, 
		AlertTriangle, 
		Wifi, 
		Settings, 
		ChevronLeft, 
		Menu,
		Activity
	} from 'lucide-svelte';

	let { children } = $props();
	let isCollapsed = $state(false);

	const navItems = [
		{ name: 'Home', path: '/', icon: Home },
		{ name: 'Production', path: '/production', icon: TrendingUp },
		{ name: 'Machine Status', path: '/machine-status', icon: Cpu },
		{ name: 'Alarm Status', path: '/alarm-status', icon: AlertTriangle },
		{ name: 'Device Status', path: '/device-status', icon: Wifi },
		{ name: 'Setting', path: '/setting', icon: Settings }
	];

	// Get active page name
	let activePageName = $derived(() => {
		const currentPath = page.url.pathname;
		const activeItem = navItems.find(item => item.path === currentPath);
		return activeItem ? activeItem.name : 'Dashboard';
	});
</script>

<svelte:head>
	<title>MMS IoT Dashboard - {activePageName()}</title>
</svelte:head>

<div class="flex h-screen w-screen overflow-hidden bg-[#0a0c10] text-[#e1e4ea] font-sans antialiased">
	<!-- Collapsible Sidebar -->
	<aside 
		class="relative flex flex-col justify-between border-r border-[#1f242f] bg-[#0d1117] transition-all duration-300 ease-in-out select-none
		{isCollapsed ? 'w-16' : 'w-64'}"
	>
		<!-- Logo Section -->
		<div class="flex h-16 items-center border-b border-[#1f242f] px-4 justify-between">
			{#if !isCollapsed}
				<div class="flex items-center gap-2 font-semibold text-lg tracking-wider text-primary">
					<Activity class="h-6 w-6 text-indigo-500 animate-pulse" />
					<span class="bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent font-bold">MMS IOT</span>
				</div>
			{/if}
			{#if isCollapsed}
				<Activity class="h-6 w-6 text-indigo-500 mx-auto animate-pulse" />
			{/if}
		</div>

		<!-- Nav Links Section -->
		<nav class="flex-1 space-y-1 py-4 px-2">
			{#each navItems as item}
				{@const IconComponent = item.icon}
				{@const isActive = page.url.pathname === item.path}
				<a 
					href={item.path}
					class="flex items-center gap-4 rounded-lg px-3 py-3 text-sm font-medium transition-all duration-150 relative group
					{isActive 
						? 'bg-indigo-600/10 text-indigo-400 border-l-4 border-indigo-500' 
						: 'text-gray-400 hover:bg-[#161b22] hover:text-gray-200'}"
				>
					<IconComponent class="h-5 w-5 shrink-0" />
					{#if !isCollapsed}
						<span class="transition-opacity duration-200">{item.name}</span>
					{/if}

					<!-- Tooltip when collapsed -->
					{#if isCollapsed}
						<div class="absolute left-full ml-4 rounded-md bg-[#161b22] border border-[#1f242f] px-2 py-1 text-xs text-gray-200 opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity whitespace-nowrap z-50 shadow-xl">
							{item.name}
						</div>
					{/if}
				</a>
			{/each}
		</nav>

		<!-- Sidebar Collapse Toggle Button -->
		<div class="p-3 border-t border-[#1f242f] flex justify-end">
			<button 
				onclick={() => isCollapsed = !isCollapsed}
				class="flex h-10 w-full items-center justify-center rounded-lg border border-[#1f242f] bg-[#161b22] text-gray-400 hover:text-gray-200 transition-colors"
				aria-label="Toggle Sidebar"
			>
				{#if isCollapsed}
					<Menu class="h-5 w-5" />
				{:else}
					<div class="flex items-center gap-2">
						<ChevronLeft class="h-5 w-5" />
						<span class="text-xs font-semibold">Collapse</span>
					</div>
				{/if}
			</button>
		</div>
	</aside>

	<!-- Main Workspace Frame -->
	<div class="flex flex-1 flex-col overflow-hidden">
		<!-- Header -->
		<header class="flex h-16 shrink-0 items-center justify-between border-b border-[#1f242f] bg-[#0d1117]/80 backdrop-blur-md px-6 z-10">
			<div class="flex items-center gap-2">
				<h1 class="text-lg font-bold tracking-tight text-white">{activePageName()}</h1>
			</div>
			
			<!-- Connection Status / System Badges -->
			<div class="flex items-center gap-4">
				<div class="flex items-center gap-2 rounded-full bg-green-500/10 px-3 py-1 text-xs font-semibold text-green-400 border border-green-500/20">
					<span class="h-2 w-2 rounded-full bg-green-500 animate-ping"></span>
					<span>ClickHouse Connected</span>
				</div>
				<div class="flex items-center gap-2 rounded-full bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-400 border border-indigo-500/20">
					<span>SSE Stream Active</span>
				</div>
			</div>
		</header>

		<!-- Scrollable Workspace Panel -->
		<main class="flex-1 overflow-y-auto bg-[#0a0c10] p-6">
			{@render children()}
		</main>
	</div>
</div>
