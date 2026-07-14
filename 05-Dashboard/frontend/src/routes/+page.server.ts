import { dashboardApiUrl } from '$lib/server/api';
import type { PageServerLoad } from './$types';

interface DeviceCount {
	process: string;
	total: number;
	online: number;
	offline: number;
	communication_fail: number;
}

export const load: PageServerLoad = async ({ fetch }) => {
	try {
		const [columnsRes, devicesRes, statusesRes, alarmsRes, healthRes] = await Promise.all([
			fetch(dashboardApiUrl('/api/v1/columns')),
			fetch(dashboardApiUrl('/api/v1/devices')),
			fetch(dashboardApiUrl('/api/v1/statuses')),
			fetch(dashboardApiUrl('/api/v1/alarms')),
			fetch(dashboardApiUrl('/health'))
		]);

		const columns = columnsRes.ok ? await columnsRes.json() : [];
		const registeredDevices = devicesRes.ok ? await devicesRes.json() : [];
		const statuses = statusesRes.ok ? await statusesRes.json() : [];
		const alarms = alarmsRes.ok ? await alarmsRes.json() : [];
		const health = healthRes.ok ? await healthRes.json() : { status: 'offline' };

		const processes = Array.from(new Set(columns.map((c: any) => c.process))) as string[];
		const deviceCounts: DeviceCount[] = await Promise.all(
			processes.map(async (process) => {
				try {
					const res = await fetch(
						dashboardApiUrl(`/api/v1/device/currently/status/${encodeURIComponent(process)}`)
					);
					if (!res.ok) {
						throw new Error(`status ${res.status}`);
					}
					const count = await res.json();
					return {
						process,
						total: Number(count.total ?? 0),
						online: Number(count.online ?? 0),
						offline: Number(count.offline ?? 0),
						communication_fail: Number(count.communication_fail ?? 0)
					};
				} catch {
					const total = registeredDevices.filter((d: any) => d.process === process).length;
					return {
						process,
						total,
						online: 0,
						offline: total,
						communication_fail: 0
					};
				}
			})
		);

		return {
			processes,
			initialProcess: processes[0] || '',
			columns,
			registeredDevices,
			statuses,
			alarms,
			deviceCounts,
			health
		};
	} catch (err) {
		console.error('Error in home server load:', err);
		return {
			processes: [],
			initialProcess: '',
			columns: [],
			registeredDevices: [],
			statuses: [],
			alarms: [],
			deviceCounts: [],
			health: { status: 'offline' }
		};
	}
};
