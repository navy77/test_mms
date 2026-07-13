<script lang="ts">
	import { onMount } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { Plus, Pencil, Trash2, Loader2 } from '@lucide/svelte';

	let apiHost = $state('localhost');
	onMount(() => {
		apiHost = window.location.hostname;
	});

	type Tab = 'users' | 'projects' | 'devices' | 'columns' | 'statuses' | 'alarms';
	let activeTab = $state<Tab>('users');

	// ── SvelteKit Server Loaded Data ──────────────────────────────────────────
	let { data } = $props();

	const usersList = $derived(data.users || []);
	const projectsList = $derived(data.projects || []);
	const devicesList = $derived(data.devices || []);
	const columnsList = $derived(data.columns || []);
	const statusesList = $derived(data.statuses || []);
	const alarmsList = $derived(data.alarms || []);

	let loading = $state(false);
	let errorMsg = $state('');

	// ── Modal State ─────────────────────────────────────────────────────────
	let modalOpen = $state(false);
	let modalMode = $state<'add' | 'edit'>('add');
	let editTarget = $state<any>(null); // For compound keys, we store the full original object

	// Form fields
	let formUser = $state({ user: '', password: '', role: 'user' as 'admin' | 'user' });
	let formProject = $state({ items: '', value: '' });
	let formDevice = $state({ process: '', device: '' });
	let formColumn = $state({ process: '', column_name: '', column_type: 'Float32', column_key: false });
	let formStatus = $state({ process: '', status: '', color: '#00cc00' });
	let formAlarm = $state({ process: '', status: '', color: '#ff9933' });

	// Helper for headers
	function getHeaders() {
		return {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${auth.accessToken ?? ''}`
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
		usersList.filter((u: any) => u.user.toLowerCase().includes(searchQuery.toLowerCase()))
	);
	const filteredProjects = $derived(
		projectsList.filter(
			(p: any) =>
				p.items.toLowerCase().includes(searchQuery.toLowerCase()) ||
				p.value.toLowerCase().includes(searchQuery.toLowerCase())
		)
	);
	const filteredDevices = $derived(
		devicesList.filter(
			(d: any) =>
				d.process.toLowerCase().includes(searchQuery.toLowerCase()) ||
				d.device.toLowerCase().includes(searchQuery.toLowerCase())
		)
	);
	const filteredColumns = $derived(
		columnsList.filter(
			(c: any) =>
				c.process.toLowerCase().includes(searchQuery.toLowerCase()) ||
				c.column_name.toLowerCase().includes(searchQuery.toLowerCase())
		)
	);
	const filteredStatuses = $derived(
		statusesList.filter(
			(s: any) =>
				s.process.toLowerCase().includes(searchQuery.toLowerCase()) ||
				s.status.toLowerCase().includes(searchQuery.toLowerCase())
		)
	);
	const filteredAlarms = $derived(
		alarmsList.filter(
			(a: any) =>
				a.process.toLowerCase().includes(searchQuery.toLowerCase()) ||
				a.status.toLowerCase().includes(searchQuery.toLowerCase())
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
		formProject = { items: '', value: '' };
		formDevice = { process: '', device: '' };
		formColumn = { process: '', column_name: '', column_type: 'Float32', column_key: false };
		formStatus = { process: '', status: 'run', color: '#00cc00' };
		formAlarm = { process: '', status: '', color: '#ff9933' };
		errorMsg = '';
		modalOpen = true;
	}

	function openEdit(item: any) {
		modalMode = 'edit';
		editTarget = item;
		if (activeTab === 'users') {
			formUser = { user: item.user, password: '', role: item.role };
		} else if (activeTab === 'projects') {
			formProject = { items: item.items, value: item.value };
		} else if (activeTab === 'devices') {
			formDevice = { process: item.process, device: item.device };
		} else if (activeTab === 'columns') {
			formColumn = { process: item.process, column_name: item.column_name, column_type: item.column_type, column_key: item.column_key || false };
		} else if (activeTab === 'statuses') {
			formStatus = { process: item.process, status: item.status, color: item.color };
		} else if (activeTab === 'alarms') {
			formAlarm = { process: item.process, status: item.status, color: item.color };
		}
		errorMsg = '';
		modalOpen = true;
	}

	async function saveModal() {
		errorMsg = '';
		loading = true;
		try {
			if (activeTab === 'users') {
				if (modalMode === 'add') {
					const res = await fetch(`http://${apiHost}:8001/api/v1/users`, {
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
					const res = await fetch(`http://${apiHost}:8001/api/v1/users/${editTarget.user}`, {
						method: 'PUT',
						headers: getHeaders(),
						body: JSON.stringify({ password: formUser.password, role: formUser.role })
					});
					if (!res.ok) {
						const details = await res.json();
						throw new Error(details.detail || 'Failed to update user');
					}
				}
			} else if (activeTab === 'projects') {
				// update only
				const res = await fetch(`http://${apiHost}:8001/api/v1/projects/${editTarget.items}`, {
					method: 'PUT',
					headers: getHeaders(),
					body: JSON.stringify({ value: formProject.value })
				});
				if (!res.ok) {
					const details = await res.json();
					throw new Error(details.detail || 'Failed to update project config');
				}
			} else if (activeTab === 'devices') {
				if (modalMode === 'add') {
					const res = await fetch(`http://${apiHost}:8001/api/v1/devices`, {
						method: 'POST',
						headers: getHeaders(),
						body: JSON.stringify(formDevice)
					});
					if (!res.ok) {
						const details = await res.json();
						throw new Error(details.detail || 'Failed to register device');
					}
				} else {
					const res = await fetch(`http://${apiHost}:8001/api/v1/devices`, {
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
					const res = await fetch(`http://${apiHost}:8001/api/v1/columns`, {
						method: 'POST',
						headers: getHeaders(),
						body: JSON.stringify(formColumn)
					});
					if (!res.ok) {
						const details = await res.json();
						throw new Error(details.detail || 'Failed to register column');
					}
				} else {
					const res = await fetch(`http://${apiHost}:8001/api/v1/columns`, {
						method: 'PUT',
						headers: getHeaders(),
						body: JSON.stringify({
							old_process: editTarget.process,
							old_column_name: editTarget.column_name,
							new_process: formColumn.process,
							new_column_name: formColumn.column_name,
							new_column_type: formColumn.column_type,
							new_column_key: formColumn.column_key
						})
					});
					if (!res.ok) {
						const details = await res.json();
						throw new Error(details.detail || 'Failed to update column');
					}
				}
			} else if (activeTab === 'statuses') {
				if (modalMode === 'add') {
					const res = await fetch(`http://${apiHost}:8001/api/v1/statuses`, {
						method: 'POST',
						headers: getHeaders(),
						body: JSON.stringify(formStatus)
					});
					if (!res.ok) {
						const details = await res.json();
						throw new Error(details.detail || 'Failed to register status');
					}
				} else {
					const res = await fetch(`http://${apiHost}:8001/api/v1/statuses`, {
						method: 'PUT',
						headers: getHeaders(),
						body: JSON.stringify({
							old_process: editTarget.process,
							old_status: editTarget.status,
							new_process: formStatus.process,
							new_status: formStatus.status,
							new_color: formStatus.color
						})
					});
					if (!res.ok) {
						const details = await res.json();
						throw new Error(details.detail || 'Failed to update status');
					}
				}
			} else if (activeTab === 'alarms') {
				if (modalMode === 'add') {
					const res = await fetch(`http://${apiHost}:8001/api/v1/alarms`, {
						method: 'POST',
						headers: getHeaders(),
						body: JSON.stringify(formAlarm)
					});
					if (!res.ok) {
						const details = await res.json();
						throw new Error(details.detail || 'Failed to register alarm');
					}
				} else {
					const res = await fetch(`http://${apiHost}:8001/api/v1/alarms`, {
						method: 'PUT',
						headers: getHeaders(),
						body: JSON.stringify({
							old_process: editTarget.process,
							old_status: editTarget.status,
							new_process: formAlarm.process,
							new_status: formAlarm.status,
							new_color: formAlarm.color
						})
					});
					if (!res.ok) {
						const details = await res.json();
						throw new Error(details.detail || 'Failed to update alarm');
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
				const res = await fetch(`http://${apiHost}:8001/api/v1/users/${item.user}`, {
					method: 'DELETE',
					headers: getHeaders()
				});
				if (!res.ok) {
					const details = await res.json();
					throw new Error(details.detail || 'Failed to delete user');
				}
			} else if (activeTab === 'devices') {
				const res = await fetch(`http://${apiHost}:8001/api/v1/devices?process=${encodeURIComponent(item.process)}&device=${encodeURIComponent(item.device)}`, {
					method: 'DELETE',
					headers: getHeaders()
				});
				if (!res.ok) {
					const details = await res.json();
					throw new Error(details.detail || 'Failed to delete device');
				}
			} else if (activeTab === 'columns') {
				const res = await fetch(`http://${apiHost}:8001/api/v1/columns?process=${encodeURIComponent(item.process)}&column_name=${encodeURIComponent(item.column_name)}`, {
					method: 'DELETE',
					headers: getHeaders()
				});
				if (!res.ok) {
					const details = await res.json();
					throw new Error(details.detail || 'Failed to delete column');
				}
			} else if (activeTab === 'statuses') {
				const res = await fetch(`http://${apiHost}:8001/api/v1/statuses?process=${encodeURIComponent(item.process)}&status=${encodeURIComponent(item.status)}`, {
					method: 'DELETE',
					headers: getHeaders()
				});
				if (!res.ok) {
					const details = await res.json();
					throw new Error(details.detail || 'Failed to delete status');
				}
			} else if (activeTab === 'alarms') {
				const res = await fetch(`http://${apiHost}:8001/api/v1/alarms?process=${encodeURIComponent(item.process)}&status=${encodeURIComponent(item.status)}`, {
					method: 'DELETE',
					headers: getHeaders()
				});
				if (!res.ok) {
					const details = await res.json();
					throw new Error(details.detail || 'Failed to delete alarm');
				}
			}
			await refreshData();
		} catch (err: any) {
			errorMsg = err.message;
		} finally {
			loading = false;
		}
	}

	const tabs = $derived([
		{ key: 'users' as Tab,     label: 'Users',    count: usersList.length },
		{ key: 'projects' as Tab,  label: 'Projects', count: projectsList.length },
		{ key: 'devices' as Tab,   label: 'Devices',  count: devicesList.length },
		{ key: 'columns' as Tab,   label: 'Columns',  count: columnsList.length },
		{ key: 'statuses' as Tab,  label: 'Statuses', count: statusesList.length },
		{ key: 'alarms' as Tab,    label: 'Alarms',   count: alarmsList.length }
	]);
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
				<span class="rounded-full bg-current/20 px-1.5 text-[10px] font-medium">{tab.count}</span>
			</button>
		{/each}
	</div>

	{#if errorMsg && !modalOpen}
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
			{#if activeTab !== 'projects'}
				<button
					onclick={openAdd}
					class="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
				>
					<Plus class="h-3 w-3" />
					Add
				</button>
			{/if}
		</div>

		<!-- Search Input Bar -->
		<div class="flex items-center gap-3 border-b border-border px-4 py-2 bg-muted/10">
			<input
				type="text"
				bind:value={searchQuery}
				placeholder={activeTab === 'users' ? 'Search by username...' : activeTab === 'projects' ? 'Search by items key...' : activeTab === 'devices' ? 'Search by process or device...' : activeTab === 'columns' ? 'Search by process or column...' : 'Search by process or status...'}
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

		<!-- Projects Table -->
		{:else if activeTab === 'projects'}
			<table class="w-full text-xs">
				<thead class="bg-muted/50">
					<tr>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Items Key</th>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Value</th>
						<th class="px-4 py-2.5 text-right font-medium text-muted-foreground">Actions</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-border">
					{#each filteredProjects as p (p.items)}
						<tr class="hover:bg-muted/30 transition-colors">
							<td class="px-4 py-2.5 font-medium text-foreground">{p.items}</td>
							<td class="px-4 py-2.5 text-muted-foreground font-mono">{p.value}</td>
							<td class="px-4 py-2.5 text-right">
								<button onclick={() => openEdit(p)} class="text-muted-foreground hover:text-foreground"><Pencil class="inline h-3 w-3" /></button>
							</td>
						</tr>
					{:else}
						<tr>
							<td colspan="3" class="px-4 py-8 text-center text-muted-foreground">No project configurations found</td>
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
		{:else if activeTab === 'columns'}
			<table class="w-full text-xs">
				<thead class="bg-muted/50">
					<tr>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Process</th>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Column Name</th>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Type</th>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Key Column</th>
						<th class="px-4 py-2.5 text-right font-medium text-muted-foreground">Actions</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-border">
					{#each paginatedColumns as c (`${c.process}-${c.column_name}`)}
						<tr class="hover:bg-muted/30 transition-colors">
							<td class="px-4 py-2.5 font-medium text-foreground">{c.process}</td>
							<td class="px-4 py-2.5 text-muted-foreground">{c.column_name}</td>
							<td class="px-4 py-2.5 font-mono text-muted-foreground">{c.column_type}</td>
							<td class="px-4 py-2.5">
								{#if c.column_key}
									<span class="inline-flex items-center rounded-md bg-amber-500/10 px-2 py-1 text-[10px] font-medium text-amber-500 ring-1 ring-inset ring-amber-500/20">Key</span>
								{:else}
									<span class="inline-flex items-center rounded-md bg-blue-500/10 px-2 py-1 text-[10px] font-medium text-blue-500 ring-1 ring-inset ring-blue-500/20">Data</span>
								{/if}
							</td>
							<td class="px-4 py-2.5 text-right">
								<button onclick={() => openEdit(c)} class="mr-2 text-muted-foreground hover:text-foreground"><Pencil class="inline h-3 w-3" /></button>
								<button onclick={() => deleteItem(c)} class="text-red-400 hover:text-red-600"><Trash2 class="inline h-3 w-3" /></button>
							</td>
						</tr>
					{:else}
						<tr>
							<td colspan="5" class="px-4 py-8 text-center text-muted-foreground">No columns registered</td>
						</tr>
					{/each}
				</tbody>
			</table>

		<!-- Statuses Table -->
		{:else if activeTab === 'statuses'}
			<table class="w-full text-xs">
				<thead class="bg-muted/50">
					<tr>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Process</th>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Status</th>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Color</th>
						<th class="px-4 py-2.5 text-right font-medium text-muted-foreground">Actions</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-border">
					{#each filteredStatuses as s (`${s.process}-${s.status}`)}
						<tr class="hover:bg-muted/30 transition-colors">
							<td class="px-4 py-2.5 font-medium text-foreground">{s.process}</td>
							<td class="px-4 py-2.5 text-muted-foreground">{s.status}</td>
							<td class="px-4 py-2.5">
								<div class="flex items-center gap-2">
									<span class="inline-block h-3.5 w-3.5 rounded-full border border-border" style="background-color: {s.color}"></span>
									<span class="font-mono text-muted-foreground">{s.color}</span>
								</div>
							</td>
							<td class="px-4 py-2.5 text-right">
								<button onclick={() => openEdit(s)} class="mr-2 text-muted-foreground hover:text-foreground"><Pencil class="inline h-3 w-3" /></button>
								<button onclick={() => deleteItem(s)} class="text-red-400 hover:text-red-600"><Trash2 class="inline h-3 w-3" /></button>
							</td>
						</tr>
					{:else}
						<tr>
							<td colspan="4" class="px-4 py-8 text-center text-muted-foreground">No statuses registered</td>
						</tr>
					{/each}
				</tbody>
			</table>

		<!-- Alarms Table -->
		{:else}
			<table class="w-full text-xs">
				<thead class="bg-muted/50">
					<tr>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Process</th>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Alarm Status</th>
						<th class="px-4 py-2.5 text-left font-medium text-muted-foreground">Color</th>
						<th class="px-4 py-2.5 text-right font-medium text-muted-foreground">Actions</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-border">
					{#each filteredAlarms as a (`${a.process}-${a.status}`)}
						<tr class="hover:bg-muted/30 transition-colors">
							<td class="px-4 py-2.5 font-medium text-foreground">{a.process}</td>
							<td class="px-4 py-2.5 text-muted-foreground">{a.status}</td>
							<td class="px-4 py-2.5">
								<div class="flex items-center gap-2">
									<span class="inline-block h-3.5 w-3.5 rounded-full border border-border" style="background-color: {a.color}"></span>
									<span class="font-mono text-muted-foreground">{a.color}</span>
								</div>
							</td>
							<td class="px-4 py-2.5 text-right">
								<button onclick={() => openEdit(a)} class="mr-2 text-muted-foreground hover:text-foreground"><Pencil class="inline h-3 w-3" /></button>
								<button onclick={() => deleteItem(a)} class="text-red-400 hover:text-red-600"><Trash2 class="inline h-3 w-3" /></button>
							</td>
						</tr>
					{:else}
						<tr>
							<td colspan="4" class="px-4 py-8 text-center text-muted-foreground">No alarms registered</td>
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

			{#if errorMsg}
				<div class="mb-4 rounded bg-destructive/10 p-2.5 text-[11px] font-medium text-destructive">
					{errorMsg}
				</div>
			{/if}

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

			{:else if activeTab === 'projects'}
				<div class="space-y-3">
					<div>
						<label class="mb-1 block text-xs text-muted-foreground">Items Key</label>
						<input bind:value={formProject.items} disabled class="w-full rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary disabled:opacity-50" />
					</div>
					<div>
						<label class="mb-1 block text-xs text-muted-foreground">Value</label>
						<input bind:value={formProject.value} class="w-full rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary" />
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

			{:else if activeTab === 'columns'}
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
					<div class="flex items-center gap-2 pt-1">
						<input type="checkbox" id="column_key" bind:checked={formColumn.column_key} class="h-4 w-4 rounded border-border bg-background text-primary focus:ring-primary focus:ring-offset-background" />
						<label for="column_key" class="text-xs font-medium text-muted-foreground cursor-pointer select-none">Is Key Column</label>
					</div>
				</div>

			{:else if activeTab === 'statuses'}
				<div class="space-y-3">
					<div>
						<label class="mb-1 block text-xs text-muted-foreground">Process</label>
						<input bind:value={formStatus.process} placeholder="e.g. demo1" class="w-full rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary" />
					</div>
					<div>
						<label class="mb-1 block text-xs text-muted-foreground">Status</label>
						<select bind:value={formStatus.status} class="w-full rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary cursor-pointer">
							<option value="run">run</option>
							<option value="alarm">alarm</option>
							<option value="wait">wait</option>
							<option value="stop">stop</option>
							<option value="other">other</option>
						</select>
					</div>
					<div>
						<label class="mb-1 block text-xs text-muted-foreground">Color</label>
						<div class="flex items-center gap-2 mt-1">
							{#each ['#FFFF00', '#FFA500', '#FF8C00', '#FF4500', '#FF0000','#8B008B','#800080','#4B0082','#0000FF','#008B8B','#008000','#ADFF2F'] as c}
								<button
									type="button"
									onclick={() => (formStatus.color = c)}
									class="h-6 w-6 rounded-full border-2 transition-all {formStatus.color === c ? 'border-primary scale-110 shadow-sm' : 'border-transparent hover:scale-105'}"
									style="background-color: {c}"
									title={c}
								></button>
							{/each}
						</div>
					</div>
				</div>

			{:else}
				<div class="space-y-3">
					<div>
						<label class="mb-1 block text-xs text-muted-foreground">Process</label>
						<input bind:value={formAlarm.process} placeholder="e.g. demo1" class="w-full rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary" />
					</div>
					<div>
						<label class="mb-1 block text-xs text-muted-foreground">Alarm Status</label>
						<input bind:value={formAlarm.status} placeholder="e.g. alarm" class="w-full rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary" />
					</div>
					<div>
						<label class="mb-1 block text-xs text-muted-foreground">Color</label>
						<div class="flex items-center gap-2 mt-1">
							{#each ['#FFFF00', '#FFA500', '#FF8C00', '#FF4500', '#FF0000','#8B008B','#800080','#4B0082','#0000FF','#008B8B','#008000','#ADFF2F'] as c}
								<button
									type="button"
									onclick={() => (formAlarm.color = c)}
									class="h-6 w-6 rounded-full border-2 transition-all {formAlarm.color === c ? 'border-primary scale-110 shadow-sm' : 'border-transparent hover:scale-105'}"
									style="background-color: {c}"
									title={c}
								></button>
							{/each}
						</div>
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
