<script lang="ts">
	import { onMount } from 'svelte';
	import { API_URLS } from '$lib/config';
	import { Settings, Users, Server, Columns, Trash2, Edit3, Plus, ShieldCheck } from 'lucide-svelte';

	// State variables using Svelte 5 runes
	let activeTab = $state('users'); // users | devices | columns
	let userRole = $state('admin');  // Default role for testing CRUD
	
	let usersList: any[] = $state([]);
	let devicesList: any[] = $state([]);
	let columnsList: any[] = $state([]);
	
	let loading = $state(false);
	let message = $state({ text: '', type: 'success' }); // success | error

	// Form Inputs
	let userForm = $state({ user: '', password: '', role: 'user' });
	let editingUser = $state<string | null>(null);

	let deviceForm = $state({ process: '', device: '' });
	let editingDevice = $state<{ old_process: string, old_device: string } | null>(null);
	let newDeviceForm = $state({ process: '', device: '' });

	let columnForm = $state({ process: '', column_name: '', column_type: 'Float64' });
	let editingColumn = $state<{ old_process: string, old_column_name: string } | null>(null);
	let newColumnForm = $state({ process: '', column_name: '', column_type: 'Float64' });

	// Trigger feedback alerts
	function showAlert(text: string, type: 'success' | 'error' = 'success') {
		message = { text, type };
		setTimeout(() => message.text = '', 4000);
	}

	// ---------------------------------------------------------------------
	// API Load Functions
	// ---------------------------------------------------------------------
	async function loadUsers() {
		try {
			const res = await fetch(`${API_URLS.dashboard}/api/users`);
			if (res.ok) usersList = await res.json();
		} catch (e) {
			console.error('Failed to load registered users:', e);
		}
	}

	async function loadDevices() {
		try {
			const res = await fetch(`${API_URLS.dashboard}/api/devices`);
			if (res.ok) devicesList = await res.json();
		} catch (e) {
			console.error('Failed to load registered devices:', e);
		}
	}

	async function loadColumns() {
		try {
			const res = await fetch(`${API_URLS.dashboard}/api/columns`);
			if (res.ok) columnsList = await res.json();
		} catch (e) {
			console.error('Failed to load registered columns:', e);
		}
	}

	function loadAllData() {
		loading = true;
		Promise.all([loadUsers(), loadDevices(), loadColumns()]).finally(() => loading = false);
	}

	onMount(() => {
		loadAllData();
	});

	// Helper to attach authorization header
	const getHeaders = () => ({
		'Content-Type': 'application/json',
		'X-Role': userRole
	});

	// ---------------------------------------------------------------------
	// User CRUD Handlers
	// ---------------------------------------------------------------------
	async function handleSaveUser() {
		try {
			if (editingUser) {
				// Update
				const res = await fetch(`${API_URLS.dashboard}/api/users/${editingUser}`, {
					method: 'PUT',
					headers: getHeaders(),
					body: JSON.stringify({ password: userForm.password, role: userForm.role })
				});
				const data = await res.json();
				if (res.ok) {
					showAlert(`User '${editingUser}' updated successfully.`);
					editingUser = null;
					userForm = { user: '', password: '', role: 'user' };
					loadUsers();
				} else {
					showAlert(data.detail || 'Failed to update user', 'error');
				}
			} else {
				// Create
				const res = await fetch(`${API_URLS.dashboard}/api/users`, {
					method: 'POST',
					headers: getHeaders(),
					body: JSON.stringify(userForm)
				});
				const data = await res.json();
				if (res.ok) {
					showAlert(`User '${userForm.user}' registered successfully.`);
					userForm = { user: '', password: '', role: 'user' };
					loadUsers();
				} else {
					showAlert(data.detail || 'Failed to register user', 'error');
				}
			}
		} catch (e: any) {
			showAlert(e.message, 'error');
		}
	}

	async function deleteUser(username: string) {
		if (!confirm(`Are you sure you want to delete user: ${username}?`)) return;
		try {
			const res = await fetch(`${API_URLS.dashboard}/api/users/${username}`, {
				method: 'DELETE',
				headers: getHeaders()
			});
			const data = await res.json();
			if (res.ok) {
				showAlert(`User '${username}' deleted.`);
				loadUsers();
			} else {
				showAlert(data.detail || 'Failed to delete user', 'error');
			}
		} catch (e: any) {
			showAlert(e.message, 'error');
		}
	}

	function startEditUser(u: any) {
		editingUser = u.user;
		userForm = { user: u.user, password: '', role: u.role };
	}

	// ---------------------------------------------------------------------
	// Device CRUD Handlers
	// ---------------------------------------------------------------------
	async function handleSaveDevice() {
		try {
			if (editingDevice) {
				// Update
				const res = await fetch(`${API_URLS.dashboard}/api/devices`, {
					method: 'PUT',
					headers: getHeaders(),
					body: JSON.stringify({
						old_process: editingDevice.old_process,
						old_device: editingDevice.old_device,
						new_process: deviceForm.process,
						new_device: deviceForm.device
					})
				});
				const data = await res.json();
				if (res.ok) {
					showAlert('Device registration updated.');
					editingDevice = null;
					deviceForm = { process: '', device: '' };
					loadDevices();
				} else {
					showAlert(data.detail || 'Failed to update device', 'error');
				}
			} else {
				// Create
				const res = await fetch(`${API_URLS.dashboard}/api/devices`, {
					method: 'POST',
					headers: getHeaders(),
					body: JSON.stringify(deviceForm)
				});
				const data = await res.json();
				if (res.ok) {
					showAlert('Device registered successfully.');
					deviceForm = { process: '', device: '' };
					loadDevices();
				} else {
					showAlert(data.detail || 'Failed to register device', 'error');
				}
			}
		} catch (e: any) {
			showAlert(e.message, 'error');
		}
	}

	async function deleteDevice(process: string, device: string) {
		if (!confirm(`Are you sure you want to delete device ${device} under process ${process}?`)) return;
		try {
			const res = await fetch(`${API_URLS.dashboard}/api/devices?process=${process}&device=${device}`, {
				method: 'DELETE',
				headers: getHeaders()
			});
			const data = await res.json();
			if (res.ok) {
				showAlert('Device registration deleted.');
				loadDevices();
			} else {
				showAlert(data.detail || 'Failed to delete device', 'error');
			}
		} catch (e: any) {
			showAlert(e.message, 'error');
		}
	}

	function startEditDevice(d: any) {
		editingDevice = { old_process: d.process, old_device: d.device };
		deviceForm = { process: d.process, device: d.device };
	}

	// ---------------------------------------------------------------------
	// Column CRUD Handlers
	// ---------------------------------------------------------------------
	async function handleSaveColumn() {
		try {
			if (editingColumn) {
				// Update
				const res = await fetch(`${API_URLS.dashboard}/api/columns`, {
					method: 'PUT',
					headers: getHeaders(),
					body: JSON.stringify({
						old_process: editingColumn.old_process,
						old_column_name: editingColumn.old_column_name,
						new_process: columnForm.process,
						new_column_name: columnForm.column_name,
						new_column_type: columnForm.column_type
					})
				});
				const data = await res.json();
				if (res.ok) {
					showAlert('Column registration updated.');
					editingColumn = null;
					columnForm = { process: '', column_name: '', column_type: 'Float64' };
					loadColumns();
				} else {
					showAlert(data.detail || 'Failed to update column', 'error');
				}
			} else {
				// Create
				const res = await fetch(`${API_URLS.dashboard}/api/columns`, {
					method: 'POST',
					headers: getHeaders(),
					body: JSON.stringify(columnForm)
				});
				const data = await res.json();
				if (res.ok) {
					showAlert('Column registered successfully.');
					columnForm = { process: '', column_name: '', column_type: 'Float64' };
					loadColumns();
				} else {
					showAlert(data.detail || 'Failed to register column', 'error');
				}
			}
		} catch (e: any) {
			showAlert(e.message, 'error');
		}
	}

	async function deleteColumn(process: string, column_name: string) {
		if (!confirm(`Are you sure you want to delete column ${column_name} under process ${process}?`)) return;
		try {
			const res = await fetch(`${API_URLS.dashboard}/api/columns?process=${process}&column_name=${column_name}`, {
				method: 'DELETE',
				headers: getHeaders()
			});
			const data = await res.json();
			if (res.ok) {
				showAlert('Column registration deleted.');
				loadColumns();
			} else {
				showAlert(data.detail || 'Failed to delete column', 'error');
			}
		} catch (e: any) {
			showAlert(e.message, 'error');
		}
	}

	function startEditColumn(c: any) {
		editingColumn = { old_process: c.process, old_column_name: c.column_name };
		columnForm = { process: c.process, column_name: c.column_name, column_type: c.column_type };
	}
</script>

<div class="space-y-6 max-w-6xl mx-auto">
	<!-- Alerts Panel -->
	{#if message.text}
		<div 
			class="rounded-xl border p-4 text-sm font-semibold transition-all shadow-md animate-bounce
			{message.type === 'success' ? 'bg-green-500/10 text-green-400 border-green-500/20' : 'bg-rose-500/10 text-rose-400 border-rose-500/20'}"
		>
			{message.text}
		</div>
	{/if}

	<!-- Top Options & Role Selector -->
	<div class="rounded-2xl border border-[#1f242f] bg-[#0d1117] p-5 shadow-lg flex flex-wrap items-center justify-between gap-4">
		<div class="flex items-center gap-3">
			<Settings class="h-6 w-6 text-indigo-500" />
			<div>
				<h2 class="text-base font-bold text-white">System Settings Wizard</h2>
				<p class="text-xs text-gray-400">Configure database tables, user access roles, and process columns</p>
			</div>
		</div>

		<!-- Simulated Role Selector to test Verify Admin validation -->
		<div class="flex items-center gap-2 bg-[#161b22] border border-[#1f242f] rounded-lg px-3 py-2">
			<ShieldCheck class="h-4 w-4 text-indigo-400" />
			<select bind:value={userRole} class="bg-transparent text-sm text-gray-200 outline-none cursor-pointer border-none p-0 focus:ring-0">
				<option value="admin" class="bg-[#161b22]">Role: Administrator (Admin)</option>
				<option value="user" class="bg-[#161b22]">Role: View Only (User)</option>
			</select>
		</div>
	</div>

	<!-- Wizard Step / Navigation Tabs -->
	<div class="flex border-b border-[#1f242f] gap-4">
		<button 
			onclick={() => activeTab = 'users'}
			class="flex items-center gap-2 px-4 py-3 text-sm font-semibold border-b-2 transition-all
			{activeTab === 'users' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-gray-400 hover:text-gray-200'}"
		>
			<Users class="h-4 w-4" />
			<span>1. Users Register</span>
		</button>
		<button 
			onclick={() => activeTab = 'devices'}
			class="flex items-center gap-2 px-4 py-3 text-sm font-semibold border-b-2 transition-all
			{activeTab === 'devices' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-gray-400 hover:text-gray-200'}"
		>
			<Server class="h-4 w-4" />
			<span>2. Devices Register</span>
		</button>
		<button 
			onclick={() => activeTab = 'columns'}
			class="flex items-center gap-2 px-4 py-3 text-sm font-semibold border-b-2 transition-all
			{activeTab === 'columns' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-gray-400 hover:text-gray-200'}"
		>
			<Columns class="h-4 w-4" />
			<span>3. Columns Register</span>
		</button>
	</div>

	<!-- Wizard Content Container -->
	<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
		
		<!-- Left / CRUD Form Panel -->
		<div class="rounded-2xl border border-[#1f242f] bg-[#0d1117] p-6 shadow-xl space-y-4">
			<h3 class="text-sm font-bold text-white uppercase tracking-wider">
				{editingUser || editingDevice || editingColumn ? 'Edit Entry' : 'Create Entry'}
			</h3>
			
			{#if activeTab === 'users'}
				<form onsubmit={handleSaveUser} class="space-y-4">
					<div class="space-y-1">
						<label class="text-xs text-gray-400 block">Username</label>
						<input 
							type="text" 
							bind:value={userForm.user} 
							disabled={editingUser !== null} 
							placeholder="Enter username" 
							required
							class="w-full bg-[#161b22] border border-[#1f242f] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 disabled:opacity-50" 
						/>
					</div>
					<div class="space-y-1">
						<label class="text-xs text-gray-400 block">Password {editingUser ? '(leave blank to keep)' : ''}</label>
						<input 
							type="password" 
							bind:value={userForm.password} 
							placeholder="Enter password" 
							required={!editingUser}
							class="w-full bg-[#161b22] border border-[#1f242f] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500" 
						/>
					</div>
					<div class="space-y-1">
						<label class="text-xs text-gray-400 block">System Role</label>
						<select 
							bind:value={userForm.role}
							class="w-full bg-[#161b22] border border-[#1f242f] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
						>
							<option value="admin">Administrator</option>
							<option value="user">User</option>
						</select>
					</div>

					<div class="flex gap-2 pt-2">
						<button 
							type="submit" 
							class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg py-2 text-sm font-semibold transition-colors flex items-center justify-center gap-1"
						>
							<Plus class="h-4 w-4" />
							<span>{editingUser ? 'Save Changes' : 'Add User'}</span>
						</button>
						{#if editingUser}
							<button 
								type="button" 
								onclick={() => { editingUser = null; userForm = { user: '', password: '', role: 'user' }; }}
								class="border border-[#1f242f] hover:bg-[#161b22] text-gray-400 rounded-lg px-4 py-2 text-sm font-semibold transition-colors"
							>
								Cancel
							</button>
						{/if}
					</div>
				</form>

			{:else if activeTab === 'devices'}
				<form onsubmit={handleSaveDevice} class="space-y-4">
					<div class="space-y-1">
						<label class="text-xs text-gray-400 block">Process Name</label>
						<input 
							type="text" 
							bind:value={deviceForm.process} 
							placeholder="e.g. demo1" 
							required
							class="w-full bg-[#161b22] border border-[#1f242f] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500" 
						/>
					</div>
					<div class="space-y-1">
						<label class="text-xs text-gray-400 block">Device Name</label>
						<input 
							type="text" 
							bind:value={deviceForm.device} 
							placeholder="e.g. no_850" 
							required
							class="w-full bg-[#161b22] border border-[#1f242f] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500" 
						/>
					</div>

					<div class="flex gap-2 pt-2">
						<button 
							type="submit" 
							class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg py-2 text-sm font-semibold transition-colors flex items-center justify-center gap-1"
						>
							<Plus class="h-4 w-4" />
							<span>{editingDevice ? 'Save Changes' : 'Register Device'}</span>
						</button>
						{#if editingDevice}
							<button 
								type="button" 
								onclick={() => { editingDevice = null; deviceForm = { process: '', device: '' }; }}
								class="border border-[#1f242f] hover:bg-[#161b22] text-gray-400 rounded-lg px-4 py-2 text-sm font-semibold transition-colors"
							>
								Cancel
							</button>
						{/if}
					</div>
				</form>

			{:else if activeTab === 'columns'}
				<form onsubmit={handleSaveColumn} class="space-y-4">
					<div class="space-y-1">
						<label class="text-xs text-gray-400 block">Process Name</label>
						<input 
							type="text" 
							bind:value={columnForm.process} 
							placeholder="e.g. demo1" 
							required
							class="w-full bg-[#161b22] border border-[#1f242f] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500" 
						/>
					</div>
					<div class="space-y-1">
						<label class="text-xs text-gray-400 block">Column Name</label>
						<input 
							type="text" 
							bind:value={columnForm.column_name} 
							placeholder="e.g. data1" 
							required
							class="w-full bg-[#161b22] border border-[#1f242f] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500" 
						/>
					</div>
					<div class="space-y-1">
						<label class="text-xs text-gray-400 block">Column Data Type</label>
						<select 
							bind:value={columnForm.column_type}
							class="w-full bg-[#161b22] border border-[#1f242f] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
						>
							<option value="Float64">Float64</option>
							<option value="Int32">Int32</option>
							<option value="String">String</option>
							<option value="DateTime">DateTime</option>
						</select>
					</div>

					<div class="flex gap-2 pt-2">
						<button 
							type="submit" 
							class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg py-2 text-sm font-semibold transition-colors flex items-center justify-center gap-1"
						>
							<Plus class="h-4 w-4" />
							<span>{editingColumn ? 'Save Changes' : 'Register Column'}</span>
						</button>
						{#if editingColumn}
							<button 
								type="button" 
								onclick={() => { editingColumn = null; columnForm = { process: '', column_name: '', column_type: 'Float64' }; }}
								class="border border-[#1f242f] hover:bg-[#161b22] text-gray-400 rounded-lg px-4 py-2 text-sm font-semibold transition-colors"
							>
								Cancel
							</button>
						{/if}
					</div>
				</form>
			{/if}
		</div>

		<!-- Right / List Panel showing current data -->
		<div class="rounded-2xl border border-[#1f242f] bg-[#0d1117] p-6 shadow-xl lg:col-span-2 space-y-4">
			<div class="flex justify-between items-center">
				<h3 class="text-sm font-bold text-white uppercase tracking-wider">Current Registrations</h3>
				<button 
					onclick={loadAllData}
					class="text-xs text-indigo-400 hover:text-indigo-300 font-semibold"
				>
					Refresh List
				</button>
			</div>

			{#if activeTab === 'users'}
				<div class="overflow-x-auto">
					<table class="w-full text-left text-xs border-collapse">
						<thead>
							<tr class="border-b border-[#1f242f] text-gray-400 font-semibold">
								<th class="py-2.5">Username</th>
								<th class="py-2.5">System Role</th>
								<th class="py-2.5">Last Update</th>
								<th class="py-2.5 text-right">Actions</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-[#1f242f]/50 text-gray-300">
							{#each usersList as u}
								<tr class="hover:bg-[#161b22]/30 transition-colors">
									<td class="py-2.5 font-semibold text-white">{u.user}</td>
									<td class="py-2.5 font-semibold text-indigo-400">{u.role}</td>
									<td class="py-2.5">{u.last_update ? new Date(u.last_update).toLocaleString() : '-'}</td>
									<td class="py-2.5 text-right flex justify-end gap-2">
										<button onclick={() => startEditUser(u)} class="p-1 hover:text-indigo-400 text-gray-400 transition-colors" title="Edit">
											<Edit3 class="h-4 w-4" />
										</button>
										<button onclick={() => deleteUser(u.user)} class="p-1 hover:text-rose-500 text-gray-400 transition-colors" title="Delete">
											<Trash2 class="h-4 w-4" />
										</button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

			{:else if activeTab === 'devices'}
				<div class="overflow-x-auto">
					<table class="w-full text-left text-xs border-collapse">
						<thead>
							<tr class="border-b border-[#1f242f] text-gray-400 font-semibold">
								<th class="py-2.5">Process Name</th>
								<th class="py-2.5">Device ID</th>
								<th class="py-2.5">Last Update</th>
								<th class="py-2.5 text-right">Actions</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-[#1f242f]/50 text-gray-300">
							{#each devicesList as d}
								<tr class="hover:bg-[#161b22]/30 transition-colors">
									<td class="py-2.5 font-semibold text-white">{d.process}</td>
									<td class="py-2.5 font-semibold text-indigo-400">{d.device}</td>
									<td class="py-2.5">{d.last_update ? new Date(d.last_update).toLocaleString() : '-'}</td>
									<td class="py-2.5 text-right flex justify-end gap-2">
										<button onclick={() => startEditDevice(d)} class="p-1 hover:text-indigo-400 text-gray-400 transition-colors" title="Edit">
											<Edit3 class="h-4 w-4" />
										</button>
										<button onclick={() => deleteDevice(d.process, d.device)} class="p-1 hover:text-rose-500 text-gray-400 transition-colors" title="Delete">
											<Trash2 class="h-4 w-4" />
										</button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

			{:else if activeTab === 'columns'}
				<div class="overflow-x-auto">
					<table class="w-full text-left text-xs border-collapse">
						<thead>
							<tr class="border-b border-[#1f242f] text-gray-400 font-semibold">
								<th class="py-2.5">Process Name</th>
								<th class="py-2.5">Column Name</th>
								<th class="py-2.5">Data Type</th>
								<th class="py-2.5 text-right">Actions</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-[#1f242f]/50 text-gray-300">
							{#each columnsList as c}
								<tr class="hover:bg-[#161b22]/30 transition-colors">
									<td class="py-2.5 font-semibold text-white">{c.process}</td>
									<td class="py-2.5 font-semibold text-indigo-400">{c.column_name}</td>
									<td class="py-2.5 font-mono text-gray-400">{c.column_type}</td>
									<td class="py-2.5 text-right flex justify-end gap-2">
										<button onclick={() => startEditColumn(c)} class="p-1 hover:text-indigo-400 text-gray-400 transition-colors" title="Edit">
											<Edit3 class="h-4 w-4" />
										</button>
										<button onclick={() => deleteColumn(c.process, c.column_name)} class="p-1 hover:text-rose-500 text-gray-400 transition-colors" title="Delete">
											<Trash2 class="h-4 w-4" />
										</button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>
	</div>
</div>
