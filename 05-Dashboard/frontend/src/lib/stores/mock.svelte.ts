// Mock data store using Svelte 5 runes
// All data is simulated – no real API calls

// ─── Types ────────────────────────────────────────────────────────────────────

export type DeviceStatus = 'online' | 'offline';
export type MachineStatus = 'running' | 'idle' | 'stopped' | 'offline';
export type AlarmSeverity = 'critical' | 'warning' | 'info';
export type AlarmState = 'active' | 'cleared';

export interface Device {
	id: string;
	process: string;
	device: string;
	mac_id: string;
	broker: number;
	modbus: number;
	status: DeviceStatus;
	lastSeen: string;
	latencyMs: number;
}

export interface Machine {
	id: string;
	process: string;
	name: string;
	status: MachineStatus;
	uptime: string;
	data1: number;
	data2: number;
	data3: number;
	data4: number;
	data5: number;
}

export interface Alarm {
	id: string;
	process: string;
	device: string;
	message: string;
	severity: AlarmSeverity;
	state: AlarmState;
	timestamp: string;
}

export interface User {
	id: string;
	user: string;
	password: string;
	role: 'admin' | 'user';
}

export interface RegisteredDevice {
	id: string;
	process: string;
	device: string;
}

export interface Column {
	id: string;
	process: string;
	column_name: string;
	column_type: string;
	column_key?: boolean;
}

// ─── Mock State ───────────────────────────────────────────────────────────────

export const devices = $state<Device[]>([
	{ id: 'd1', process: 'demo1', device: 'no_1', mac_id: 'mac-1', broker: 1, modbus: 1, status: 'online', lastSeen: '2026-07-07T22:30:00', latencyMs: 12 },
	{ id: 'd2', process: 'demo1', device: 'no_2', mac_id: 'mac-2', broker: 1, modbus: 2, status: 'online', lastSeen: '2026-07-07T22:30:00', latencyMs: 18 },
	{ id: 'd3', process: 'demo1', device: 'no_3', mac_id: 'mac-3', broker: 1, modbus: 3, status: 'offline', lastSeen: '2026-07-07T21:55:00', latencyMs: 0 },
	{ id: 'd4', process: 'demo1', device: 'no_4', mac_id: 'mac-4', broker: 2, modbus: 1, status: 'online', lastSeen: '2026-07-07T22:29:58', latencyMs: 9 },
	{ id: 'd5', process: 'demo1', device: 'no_5', mac_id: 'mac-5', broker: 2, modbus: 2, status: 'offline', lastSeen: '2026-07-07T22:10:00', latencyMs: 0 },
	{ id: 'd6', process: 'demo2', device: 'no_1', mac_id: 'mac-6', broker: 1, modbus: 1, status: 'online', lastSeen: '2026-07-07T22:30:00', latencyMs: 22 },
	{ id: 'd7', process: 'demo2', device: 'no_2', mac_id: 'mac-7', broker: 1, modbus: 2, status: 'online', lastSeen: '2026-07-07T22:29:55', latencyMs: 14 },
	{ id: 'd8', process: 'demo2', device: 'no_3', mac_id: 'mac-8', broker: 2, modbus: 3, status: 'offline', lastSeen: '2026-07-07T20:00:00', latencyMs: 0 },
]);

export const machines = $state<Machine[]>([
	{ id: 'm1', process: 'demo1', name: 'Machine A', status: 'running', uptime: '08h 32m', data1: 92, data2: 87, data3: 450, data4: 1.2, data5: 65 },
	{ id: 'm2', process: 'demo1', name: 'Machine B', status: 'idle',    uptime: '08h 32m', data1: 0,  data2: 0,  data3: 400, data4: 1.0, data5: 60 },
	{ id: 'm3', process: 'demo1', name: 'Machine C', status: 'stopped', uptime: '03h 10m', data1: 0,  data2: 0,  data3: 0,   data4: 0,   data5: 0 },
	{ id: 'm4', process: 'demo2', name: 'Machine D', status: 'running', uptime: '08h 32m', data1: 78, data2: 81, data3: 510, data4: 1.3, data5: 72 },
	{ id: 'm5', process: 'demo2', name: 'Machine E', status: 'running', uptime: '07h 45m', data1: 88, data2: 92, data3: 488, data4: 1.1, data5: 68 },
	{ id: 'm6', process: 'demo2', name: 'Machine F', status: 'offline', uptime: '00h 00m', data1: 0,  data2: 0,  data3: 0,   data4: 0,   data5: 0 },
]);

export const alarms = $state<Alarm[]>([
	{ id: 'a1', process: 'demo1', device: 'no_3', message: 'Device offline — no heartbeat for >5 min', severity: 'critical', state: 'active',  timestamp: '2026-07-07T22:05:00' },
	{ id: 'a2', process: 'demo1', device: 'no_5', message: 'Device offline — no heartbeat for >5 min', severity: 'critical', state: 'active',  timestamp: '2026-07-07T22:15:00' },
	{ id: 'a3', process: 'demo2', device: 'no_3', message: 'Device offline — no heartbeat for >120 min', severity: 'warning', state: 'active', timestamp: '2026-07-07T20:05:00' },
	{ id: 'a4', process: 'demo1', device: 'no_1', message: 'High temperature threshold exceeded (data3 > 500)', severity: 'warning', state: 'cleared', timestamp: '2026-07-07T18:40:00' },
	{ id: 'a5', process: 'demo1', device: 'no_2', message: 'Modbus timeout — retried 3 times', severity: 'info', state: 'cleared', timestamp: '2026-07-07T16:00:00' },
	{ id: 'a6', process: 'demo2', device: 'no_1', message: 'Broker disconnected briefly', severity: 'info', state: 'cleared', timestamp: '2026-07-07T14:22:00' },
]);

export const users = $state<User[]>([
	{ id: 'u1', user: 'admin', password: '••••••', role: 'admin' },
	{ id: 'u2', user: 'user',  password: '••••••', role: 'user' },
]);

export const registeredDevices = $state<RegisteredDevice[]>([
	{ id: 'rd1', process: 'demo1', device: 'no_1' },
	{ id: 'rd2', process: 'demo1', device: 'no_2' },
	{ id: 'rd3', process: 'demo1', device: 'no_3' },
	{ id: 'rd4', process: 'demo1', device: 'no_4' },
	{ id: 'rd5', process: 'demo1', device: 'no_5' },
	{ id: 'rd6', process: 'demo2', device: 'no_1' },
	{ id: 'rd7', process: 'demo2', device: 'no_2' },
	{ id: 'rd8', process: 'demo2', device: 'no_3' },
]);

export const columns = $state<Column[]>([
	{ id: 'c0', process: 'demo1', column_name: 'model', column_type: 'String', column_key: true },
	{ id: 'c1', process: 'demo1', column_name: 'data1', column_type: 'Float32', column_key: false },
	{ id: 'c2', process: 'demo1', column_name: 'data2', column_type: 'Float32', column_key: false },
	{ id: 'c3', process: 'demo1', column_name: 'data3', column_type: 'Float32', column_key: false },
	{ id: 'c4', process: 'demo1', column_name: 'data4', column_type: 'Float32', column_key: false },
	{ id: 'c5', process: 'demo1', column_name: 'data5', column_type: 'Float32', column_key: false },
	{ id: 'c6', process: 'demo2', column_name: 'data1', column_type: 'Float32', column_key: false },
	{ id: 'c7', process: 'demo2', column_name: 'data2', column_type: 'Float32', column_key: false },
]);

// ─── Derived Stats (computed) ─────────────────────────────────────────────────

export function getStats() {
	const totalDevices = devices.length;
	const onlineDevices = devices.filter((d) => d.status === 'online').length;
	const offlineDevices = totalDevices - onlineDevices;
	const activeAlarms = alarms.filter((a) => a.state === 'active').length;
	const runningMachines = machines.filter((m) => m.status === 'running').length;

	return { totalDevices, onlineDevices, offlineDevices, activeAlarms, runningMachines };
}
