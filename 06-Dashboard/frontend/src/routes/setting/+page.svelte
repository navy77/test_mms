<script lang="ts">
	import { onMount } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { Plus, Pencil, Trash2, Loader2 } from '@lucide/svelte';

	type Tab = 'users' | 'devices' | 'columns';
	let activeTab = $state<Tab>('users');

	// ── SvelteKit Server Loaded Data ──────────────────────────────────────────
	let { data } = $props();

	const usersList = $derived(data.users || []);
	const devicesList = $derived(data.devices || []);
	const columnsList = $derived(data.columns || []);

	let loading = $state(false);
	let errorMsg = $state('');

	// ── Modal State ─────────────────────────────────────────────────────────
	let modalOpen = $state(false);
	let modalMode = $state<'add' | 'edit'>('add');
	let editTarget = $state<any>(null); // For compound keys, we store the full original object

	// Form fields
	let formUser = $state({ user: '', password: '', role: 'user' as 'admin' | 'user' });
	let formDevice = $state({ process: '', device: '' });
	let formColumn = $state({ process: '', column_name: '', column_type: 'Float32' });

	// Helper for headers
	function getHeaders() {
		return {
			'Content-Type': 'application/json',
			'X-Role': auth.user?.role || 'user'
		};
	}

	async function refreshData() {
		loading = true;
		errorMsg = '';
		try {
			await invalidateAll();
		} catch (err: any) {
			errorMsg = err.message || 'Failed to refresh data';
		} finally {
			loading = false;
		}
	}

	let searchQuery = $state('');

	// Computed filtered variables
	const filteredUsers = $derived(
		usersList.filter((u) => u.user.toLowerCase().includes(searchQuery.toLowerCase()))
	);
	const filteredDevices = $derived(
		devicesList.filter(
			(d) =>
				d.process.toLowerCase().includes(searchQuery.toLowerCase()) ||
				d.device.toLowerCase().includes(searchQuery.toLowerCase())
		)
	);
	const filteredColumns = $derived(
		columnsList.filter(
			(c) =>
				c.process.toLowerCase().includes(searchQuery.toLowerCase()) ||
				c.column_name.toLowerCase().includes(searchQuery.toLowerCase())
		)
	);

	// ── Pagination States ────────────────────────────────────────────────────
	let devicesPage = $state(1);
	let columnsPage = $state(1);
	const pageSize = 10;

	// Computed pagination variables
	const paginatedDevices = $derived(filteredDevices.slice((devicesPage - 1) * pageSize, devicesPage * pageSize));
	const paginatedColumns = $derived(filteredColumns.slice((columnsPage - 1) * pageSize, columnsPage * pageSize));

	const totalDevicesPages = $derived(Math.ceil(filteredDevices.length / pageSize) || 1);
	const totalColumnsPages = $derived(Math.ceil(filteredColumns.length / pageSize) || 1);

	// Fetch and reset pagination on tab change
	$effect(() => {
		activeTab;
		devicesPage = 1;
		columnsPage = 1;
		searchQuery = '';
		refreshData();
	});

	// ── CRUD Action Handlers ────────────────────────────────────────────────
	function openAdd() {
		modalMode = 'add';
		editTarget = null;
		formUser = { user: '', password: '', role: 'user' };
		formDevice = { process: '', device: '' };
		formColumn = { process: '', column_name: '', column_type: 'Float32' };
		modalOpen = true;
	}

	function openEdit(item: any) {
		modalMode = 'edit';
		editTarget = item;
		if (activeTab === 'users') {
			formUser = { user: item.user, password: '', role: item.role };
		} else if (activeTab === 'devices') {
			formDevice = { process: item.process, device: item.device };
		} else if (activeTab === 'columns') {
			formColumn = { process: item.process, column_name: item.column_name, column_type: item.column_type };
		}
		modalOpen = true;
	}

	async function saveModal() {
		errorMsg = '';
		loading = true;
		try {
			if (activeTab === 'users') {
				if (modalMode === 'add') {
					const res = await fetch('http://localhost:8001/api/users', {
						method: 'POST',
						headers: getHeaders(),
						body: JSON.stringify(formUser)
					});
					if (!res.ok) {
						const details = await res.json();
						throw new Error(details.detail || 'Failed to create user');
					}
				} else {
					// update user
					const res = await fetch(`http://localhost:8001/api/users/${editTarget.user}`, {
						method: 'PUT',
						headers: getHeaders(),
						body: JSON.stringify({ password: formUser.password, role: formUser.role })
					});
					if (!res.ok) {
						const details = await res.json();
						throw new Error(details.detail || 'Failed to update user');
					}
				}
			} else if (activeTab === 'devices') {
				if (modalMode === 'add') {
					const res = await fetch('http://localhost:8001/api/devices', {
						method: 'POST',
						headers: getHeaders(),
						body: JSON.stringify(formDevice)
					});
					if (!res.ok) {
						const details = await res.json();
						throw new Error(details.detail || 'Failed to register device');
					}
				} else {
					const res = await fetch('http://localhost:8001/api/devices', {
						method: 'PUT',
						headers: getHeaders(),
						body: JSON.stringify({
							old_process: editTarget.process,
							old_device: editTarget.device,
							new_process: formDevice.process,
							new_device: formDevice.device
						})
					});
					if (!res.ok) {
						const details = await res.json();
						throw new Error(details.detail || 'Failed to update device');
					}
				}
			} else if (activeTab === 'columns') {
				if (modalMode === 'add') {
					const res = await fetch('http://localhost:8001/api/columns', {
						method: 'POST',
						headers: getHeaders(),
						body: JSON.stringify(formColumn)
					});
					if (!res.ok) {
						const details = await res.json();
						throw new Error(details.detail || 'Failed to register column');
					}
				} else {
					const res = await fetch('http://localhost:8001/api/columns', {
						method: 'PUT',
						headers: getHeaders(),
						body: JSON.stringify({
							old_process: editTarget.process,
							old_column_name: editTarget.column_name,
							new_process: formColumn.process,
							new_column_name: formColumn.column_name,
							new_column_type: formColumn.column_type
						})
					});
					if (!res.ok) {
						const details = await res.json();
						throw new Error(details.detail || 'Failed to update column');
					}
				}
			}
			modalOpen = false;
			await refreshData();
		} catch (err: any) {
			errorMsg = err.message;
		} finally {
			loading = false;
		}
	}

	async function deleteItem(item: any) {
		if (!confirm('Are you sure you want to delete this item?')) return;
		errorMsg = '';
		loading = true;
		try {
			if (activeTab === 'users') {
				const res = await fetch(`http://localhost:8001/api/users/${item.user}`, {
					method: 'DELETE',
					headers: getHeaders()
				});
				if (!res.ok) {
					const details = await res.json();
					throw new Error(details.detail || 'Failed to delete user');
				}
			} else if (activeTab === 'devices') {
				const res = await fetch(`http://localhost:8001/api/devices?process=${encodeURIComponent(item.process)}&device=${encodeURIComponent(item.device)}`, {
					method: 'DELETE',
					headers: getHeaders()
				});
				if (!res.ok) {
					const details = await res.json();
					throw new Error(details.detail || 'Failed to delete device');
				}
			} else if (activeTab === 'columns') {
				const res = await fetch(`http://localhost:8001/api/columns?process=${encodeURIComponent(item.process)}&column_name=${encodeURIComponent(item.column_name)}`, {
					method: 'DELETE',
					headers: getHeaders()
				});
				if (!res.ok) {
					const details = await res.json();
					throw new Error(details.detail || 'Failed to delete column');
				}
			}
			await refreshData();
		} catch (err: any) {
			errorMsg = err.message;
		} finally {
			loading = false;
		}
	}

	const tabs = [
		{ key: 'users' as Tab,   label: 'Users',   count: () => usersList.length },
		{ key: 'devices' as Tab, label: 'Devices', count: () => devicesList.length },
		{ key: 'columns' as Tab, label: 'Columns', count: () => columnsList.length }
	];
</script>

<div class="space-y-4">
	<!-- Wizard Tabs -->
	<div class="flex items-center gap-1 rounded-lg border border-border bg-card p-1 w-fit">
		{#each tabs as tab}
			<button
				onclick={() => (activeTab = tab.key)}
				class="flex items-center gap-1.5 rounded-md px-4 py-1.5 text-sm transition-colors {activeTab === tab.key
					? 'bg-primary text-primary-foreground'
					: 'text-muted-foreground hover:text-foreground'}"
			>
				{tab.label}
				<span class="rounded-full bg-current/20 px-1.5 text-[10px] font-medium">{tab.count()}</span>
			</button>
		{/each}
	</div>

	{#if errorMsg}
		<div class="rounded-md bg-destructive/10 p-3 text-xs font-medium text-destructive">
			{errorMsg}
		</div>
	{/if}

	<!-- Table + Add Button -->
	<div class="rounded-lg border border-border bg-card overflow-hidden">
		<div class="flex items-center justify-between border-b border-border px-4 py-3">
			<div class="flex items-center gap-2">
				<h2 class="text-sm font-semibold text-card-foreground capitalize">{activeTab} Register</h2>
				{#if loading}
					<Loader2 class="h-4 w-4 animate-spin text-muted-foreground" />
				{/if}
			</div>
			<button
				onclick={openAdd}
				class="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
			>
				<Plus class="h-3 w-3" />
				Add
			</button>
		</div>

		<!-- Search Input Bar -->
		<div class="flex items-center gap-3 border-b border-border px-4 py-2 bg-muted/10">
			<input
				type="text"
				bind:value={searchQuery}
				placeholder={activeTab === 'users' ? 'Search by username...' : activeTab === 'devices' ? 'Search by process or device...' : 'Search by process or column...'}
				class="flex-1 max-w-sm rounded border border-border bg-background px-3 py-1.5 text-xs text-foreground outline-none focus:border-primary placeholder:text-muted-foreground"
			/>
		</div>

		<!-- Users Table -->
		{#if activeTab === 'users'}
			<table class="w-full text-xs">
				<thead class="bg-muted/50">
					<tr>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Username</th>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Role</th>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Password</th>
						<th class="px-4 py-2.5 text-right font-medium text-muted-foreground">Actions</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-border">
					{#each filteredUsers as u (u.user)}
						<tr class="hover:bg-muted/30 transition-colors">
							<td class="px-4 py-2.5 font-medium text-foreground">{u.user}</td>
							<td class="px-4 py-2.5">
								<span class="rounded-full px-2 py-0.5 text-[10px] font-medium uppercase {u.role === 'admin' ? 'bg-purple-500/10 text-purple-600 dark:text-purple-400' : 'bg-blue-500/10 text-blue-600 dark:text-blue-400'}">{u.role}</span>
							</td>
							<td class="px-4 py-2.5 text-muted-foreground font-mono">••••••</td>
							<td class="px-4 py-2.5 text-right">
								<button onclick={() => openEdit(u)} class="mr-2 text-muted-foreground hover:text-foreground"><Pencil class="inline h-3 w-3" /></button>
								<button onclick={() => deleteItem(u)} class="text-red-400 hover:text-red-600"><Trash2 class="inline h-3 w-3" /></button>
							</td>
						</tr>
					{:else}
						<tr>
							<td colspan="4" class="px-4 py-8 text-center text-muted-foreground">No users found</td>
						</tr>
					{/each}
				</tbody>
			</table>

		<!-- Devices Table -->
		{:else if activeTab === 'devices'}
			<table class="w-full text-xs">
				<thead class="bg-muted/50">
					<tr>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Process</th>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Device</th>
						<th class="px-4 py-2.5 text-right font-medium text-muted-foreground">Actions</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-border">
					{#each paginatedDevices as d (`${d.process}-${d.device}`)}
						<tr class="hover:bg-muted/30 transition-colors">
							<td class="px-4 py-2.5 font-medium text-foreground">{d.process}</td>
							<td class="px-4 py-2.5 text-muted-foreground">{d.device}</td>
							<td class="px-4 py-2.5 text-right">
								<button onclick={() => openEdit(d)} class="mr-2 text-muted-foreground hover:text-foreground"><Pencil class="inline h-3 w-3" /></button>
								<button onclick={() => deleteItem(d)} class="text-red-400 hover:text-red-600"><Trash2 class="inline h-3 w-3" /></button>
							</td>
						</tr>
					{:else}
						<tr>
							<td colspan="3" class="px-4 py-8 text-center text-muted-foreground">No devices registered</td>
						</tr>
					{/each}
				</tbody>
			</table>

		<!-- Columns Table -->
		{:else}
			<table class="w-full text-xs">
				<thead class="bg-muted/50">
					<tr>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Process</th>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Column Name</th>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Type</th>
						<th class="px-4 py-2.5 text-right font-medium text-muted-foreground">Actions</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-border">
					{#each paginatedColumns as c (`${c.process}-${c.column_name}`)}
						<tr class="hover:bg-muted/30 transition-colors">
							<td class="px-4 py-2.5 font-medium text-foreground">{c.process}</td>
							<td class="px-4 py-2.5 text-muted-foreground">{c.column_name}</td>
							<td class="px-4 py-2.5 font-mono text-muted-foreground">{c.column_type}</td>
							<td class="px-4 py-2.5 text-right">
								<button onclick={() => openEdit(c)} class="mr-2 text-muted-foreground hover:text-foreground"><Pencil class="inline h-3 w-3" /></button>
								<button onclick={() => deleteItem(c)} class="text-red-400 hover:text-red-600"><Trash2 class="inline h-3 w-3" /></button>
							</td>
						</tr>
					{:else}
						<tr>
							<td colspan="4" class="px-4 py-8 text-center text-muted-foreground">No columns registered</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}

		<!-- Pagination Footer for Devices & Columns -->
		{#if activeTab === 'devices' || activeTab === 'columns'}
			{@const curPage = activeTab === 'devices' ? devicesPage : columnsPage}
			{@const totPages = activeTab === 'devices' ? totalDevicesPages : totalColumnsPages}
			{@const listLen = activeTab === 'devices' ? devicesList.length : columnsList.length}
			<div class="flex items-center justify-between border-t border-border px-4 py-2.5 bg-muted/20">
				<p class="text-xs text-muted-foreground">
					Showing {listLen > 0 ? (curPage - 1) * pageSize + 1 : 0} to {Math.min(curPage * pageSize, listLen)} of {listLen} rows
				</p>
				<div class="flex items-center gap-1.5">
					<button
						onclick={() => {
							if (activeTab === 'devices') devicesPage = Math.max(1, devicesPage - 1);
							else columnsPage = Math.max(1, columnsPage - 1);
						}}
						disabled={curPage === 1}
						class="rounded border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted disabled:opacity-50"
					>
						Previous
					</button>
					<span class="text-xs text-muted-foreground px-2">Page {curPage} of {totPages}</span>
					<button
						onclick={() => {
							if (activeTab === 'devices') devicesPage = Math.min(totalDevicesPages, devicesPage + 1);
							else columnsPage = Math.min(totalColumnsPages, columnsPage + 1);
						}}
						disabled={curPage === totPages}
						class="rounded border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted disabled:opacity-50"
					>
						Next
					</button>
				</div>
			</div>
		{/if}
	</div>
</div>

<!-- Modal -->
{#if modalOpen}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
		<div class="w-full max-w-sm rounded-lg border border-border bg-card p-6 shadow-xl animate-in fade-in zoom-in-95 duration-150">
			<h3 class="mb-4 text-sm font-semibold text-card-foreground capitalize">
				{modalMode === 'add' ? 'Add' : 'Edit'} {activeTab.slice(0, -1)}
			</h3>

			{#if activeTab === 'users'}
				<div class="space-y-3">
					<div>
						<label class="mb-1 block text-xs text-muted-foreground">Username</label>
						<input bind:value={formUser.user} disabled={modalMode === 'edit'} class="w-full rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary disabled:opacity-50" />
					</div>
					<div>
						<label class="mb-1 block text-xs text-muted-foreground">{modalMode === 'edit' ? 'New Password' : 'Password'}</label>
						<input type="password" bind:value={formUser.password} class="w-full rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary" />
					</div>
					<div>
						<label class="mb-1 block text-xs text-muted-foreground">Role</label>
						<select bind:value={formUser.role} class="w-full rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary">
							<option value="admin">admin</option>
							<option value="user">user</option>
						</select>
					</div>
				</div>

			{:else if activeTab === 'devices'}
				<div class="space-y-3">
					<div>
						<label class="mb-1 block text-xs text-muted-foreground">Process</label>
						<input bind:value={formDevice.process} placeholder="e.g. demo1" class="w-full rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary" />
					</div>
					<div>
						<label class="mb-1 block text-xs text-muted-foreground">Device</label>
						<input bind:value={formDevice.device} placeholder="e.g. no_1" class="w-full rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary" />
					</div>
				</div>

			{:else}
				<div class="space-y-3">
					<div>
						<label class="mb-1 block text-xs text-muted-foreground">Process</label>
						<input bind:value={formColumn.process} placeholder="e.g. demo1" class="w-full rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary" />
					</div>
					<div>
						<label class="mb-1 block text-xs text-muted-foreground">Column Name</label>
						<input bind:value={formColumn.column_name} placeholder="e.g. data1" class="w-full rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary" />
					</div>
					<div>
						<label class="mb-1 block text-xs text-muted-foreground">Column Type</label>
						<select bind:value={formColumn.column_type} class="w-full rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary">
							<option>Float32</option>
							<option>Float64</option>
							<option>String</option>
							<option>Int32</option>
							<option>UInt32</option>
						</select>
					</div>
				</div>
			{/if}

			<div class="mt-5 flex justify-end gap-2">
				<button onclick={() => (modalOpen = false)} class="rounded border border-border px-4 py-1.5 text-xs text-muted-foreground hover:bg-muted transition-colors">Cancel</button>
				<button onclick={saveModal} class="rounded bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors">Save</button>
			</div>
		</div>
	</div>
{/if}
