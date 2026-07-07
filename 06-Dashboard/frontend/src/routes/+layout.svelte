<script lang="ts">
	import './layout.css';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import {
		LayoutDashboard,
		Factory,
		Cpu,
		Bell,
		HardDrive,
		Settings,
		ChevronLeft,
		ChevronRight,
		Moon,
		Sun,
		Activity,
		LogOut
	} from '@lucide/svelte';

	let { children } = $props();

	let sidebarCollapsed = $state(false);
	let darkMode = $state(false);

	const navItems = $derived([
		{ href: '/', label: 'Home', icon: LayoutDashboard },
		{ href: '/production', label: 'Production', icon: Factory },
		{ href: '/machine-status', label: 'Machine Status', icon: Cpu },
		{ href: '/alarm-status', label: 'Alarm Status', icon: Bell },
		{ href: '/device-status', label: 'Device Status', icon: HardDrive },
		...(auth.user?.role === 'admin' ? [{ href: '/setting', label: 'Setting', icon: Settings }] : [])
	]);

	$effect(() => {
		if (darkMode) {
			document.documentElement.classList.add('dark');
		} else {
			document.documentElement.classList.remove('dark');
		}
	});

	$effect(() => {
		// Route Protection
		if (!auth.isLoggedIn && $page.url.pathname !== '/login') {
			goto('/login');
		} else if (auth.isLoggedIn) {
			if ($page.url.pathname === '/login') {
				goto('/');
			} else if ($page.url.pathname.startsWith('/setting') && auth.user?.role !== 'admin') {
				goto('/'); // Redirect non-admins away from settings
			}
		}
	});

	function isActive(href: string) {
		if (href === '/') return $page.url.pathname === '/';
		return $page.url.pathname.startsWith(href);
	}
</script>

<svelte:head>
	<title>MMS IoT Dashboard</title>
	<meta name="description" content="Industrial IoT monitoring dashboard for machine, device, and alarm status" />
</svelte:head>

{#if $page.url.pathname === '/login'}
	{@render children()}
{:else if auth.isLoggedIn}
	<div class="flex h-screen overflow-hidden bg-background">
		<!-- Sidebar -->
		<aside
			class="flex flex-col border-r border-border bg-sidebar transition-all duration-300 {sidebarCollapsed ? 'w-16' : 'w-56'}"
		>
			<!-- Logo / Brand + Collapse Button -->
			<div class="flex h-14 items-center border-b border-border px-3">
				{#if !sidebarCollapsed}
					<div class="flex flex-1 items-center gap-2">
						<Activity class="h-5 w-5 text-primary" />
						<span class="text-sm font-semibold tracking-tight text-sidebar-foreground">MMS Monitor</span>
					</div>
					<button
						onclick={() => (sidebarCollapsed = !sidebarCollapsed)}
						class="ml-auto rounded-md p-1 text-sidebar-foreground/50 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
						title="Collapse"
					>
						<ChevronLeft class="h-4 w-4" />
					</button>
				{:else}
					<button
						onclick={() => (sidebarCollapsed = !sidebarCollapsed)}
						class="mx-auto rounded-md p-1 text-sidebar-foreground/50 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
						title="Expand"
					>
						<ChevronRight class="h-4 w-4" />
					</button>
				{/if}
			</div>

			<!-- Nav Items -->
			<nav class="flex flex-1 flex-col gap-1 p-2">
				{#each navItems as item}
					{@const active = isActive(item.href)}
					<a
						href={item.href}
						class="flex items-center gap-3 rounded-md px-2 py-2 text-sm transition-colors
							{active
								? 'bg-sidebar-primary text-sidebar-primary-foreground'
								: 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'}
							{sidebarCollapsed ? 'justify-center' : ''}"
						title={sidebarCollapsed ? item.label : ''}
					>
						<item.icon class="h-4 w-4 shrink-0" />
						{#if !sidebarCollapsed}
							<span>{item.label}</span>
						{/if}
					</a>
				{/each}
			</nav>

			<!-- Bottom Controls -->
			<div class="flex flex-col gap-1 border-t border-border p-2">
				<!-- Dark Mode Toggle -->
				<button
					onclick={() => (darkMode = !darkMode)}
					class="flex items-center gap-3 rounded-md px-2 py-2 text-sm text-sidebar-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground {sidebarCollapsed ? 'justify-center' : ''}"
					title={darkMode ? 'Light Mode' : 'Dark Mode'}
				>
					{#if darkMode}
						<Sun class="h-4 w-4 shrink-0" />
					{:else}
						<Moon class="h-4 w-4 shrink-0" />
					{/if}
					{#if !sidebarCollapsed}
						<span>{darkMode ? 'Light Mode' : 'Dark Mode'}</span>
					{/if}
				</button>

				<!-- Sign Out -->
				<button
					onclick={() => { auth.logout(); goto('/login'); }}
					class="flex items-center gap-3 rounded-md px-2 py-2 text-sm text-500 transition-colors hover:bg-red-500/10 {sidebarCollapsed ? 'justify-center' : ''}"
					title="Sign Out"
				>
					<LogOut class="h-4 w-4 shrink-0" />
					{#if !sidebarCollapsed}
						<span>Sign Out</span>
					{/if}
				</button>
			</div>
		</aside>

		<!-- Main Content -->
		<main class="flex flex-1 flex-col overflow-hidden">
			<!-- Topbar -->
			<header class="flex h-14 items-center border-b border-border bg-background px-6">
				<h1 class="text-sm font-medium text-muted-foreground">
					{#each navItems as item}
						{#if isActive(item.href)}
							{item.label}
						{/if}
					{/each}
				</h1>
				<div class="ml-auto flex items-center gap-4">
					{#if auth.user}
						<span class="text-xs text-muted-foreground">
							Logged in as: <strong class="text-foreground">{auth.user.username}</strong> ({auth.user.role})
						</span>
					{/if}
					<span class="inline-flex items-center gap-1.5 rounded-full bg-green-500/10 px-2 py-0.5 text-xs font-medium text-green-600 dark:text-green-400">
						<span class="h-1.5 w-1.5 animate-pulse rounded-full bg-green-500"></span>
						Live
					</span>
				</div>
			</header>

			<!-- Page Content -->
			<div class="flex-1 overflow-auto p-6">
				{@render children()}
			</div>
		</main>
	</div>
{:else}
	<div class="flex h-screen items-center justify-center bg-background">
		<div class="text-center space-y-2">
			<Activity class="h-8 w-8 animate-pulse text-primary mx-auto" />
			<p class="text-sm text-muted-foreground">Redirecting to login...</p>
		</div>
	</div>
{/if}
