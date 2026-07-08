<script lang="ts">
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { Activity, Loader2 } from '@lucide/svelte';
	import { fade, fly } from 'svelte/transition';

	let username = $state('');
	let password = $state('');
	let errorMsg = $state('');
	let loading = $state(false);

	async function handleLogin(e: SubmitEvent) {
		e.preventDefault();
		if (!username || !password) {
			errorMsg = 'Please fill in both fields.';
			return;
		}

		errorMsg = '';
		loading = true;

		try {
			// Connect to backend api at port 8001
			const res = await fetch('http://localhost:8001/auth/login', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({ username, password })
			});

			if (!res.ok) {
				const errorData = await res.json();
				throw new Error(errorData.detail || 'Login failed');
			}

			const data = await res.json();
			if (data.success) {
				auth.login({
					username: data.username,
					role: data.role
				});
				goto('/');
			} else {
				throw new Error('Authentication failed');
			}
		} catch (err: any) {
			errorMsg = err.message || 'Connection failed. Please try again.';
		} finally {
			loading = false;
		}
	}
</script>

<div class="flex min-h-screen items-center justify-center bg-background px-4">
	<div in:fly={{ y: 50, duration: 1000 }} class="w-full max-w-sm rounded-lg border border-border bg-card p-6 shadow-md transition-all duration-300">
		<div class="mb-6 text-center">
			<div class="inline-flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 transition-transform duration-500 {loading ? 'scale-110' : ''}">
				{#if loading}
					<Loader2 class="h-6 w-6 text-primary animate-spin" />
				{:else}
					<Activity class="h-6 w-6 text-primary" />
				{/if}
			</div>
			<h2 class="mt-3 text-lg font-semibold text-card-foreground">MMS Monitor Login</h2>
			<p class="text-xs text-muted-foreground">Sign in to access your IoT Dashboard</p>
		</div>

		{#if errorMsg}
			<div transition:fade={{ duration: 1000 }} class="mb-4 rounded-md bg-destructive/10 p-3 text-xs font-medium text-destructive">
				{errorMsg}
			</div>
		{/if}

		<form onsubmit={handleLogin} class="space-y-4">
			<div>
				<label for="username" class="mb-1 block text-xs font-medium text-muted-foreground">Username</label>
				<input
					id="username"
					bind:value={username}
					type="text"
					class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
					placeholder="Enter username"
					required
					disabled={loading}
				/>
			</div>

			<div>
				<label for="password" class="mb-1 block text-xs font-medium text-muted-foreground">Password</label>
				<input
					id="password"
					bind:value={password}
					type="password"
					class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
					placeholder="Enter password"
					required
					disabled={loading}
				/>
			</div>

			<button
				type="submit"
				class="w-full rounded-md bg-primary py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
				disabled={loading}
			>
				{loading ? 'Authenticating...' : 'Sign In'}
			</button>
		</form>
	</div>
</div>
