import { dashboardApiUrl } from '$lib/server/api';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	try {
		// 1. Fetch columns to extract unique processes
		const columnsRes = await fetch(dashboardApiUrl('/api/v1/columns'));
		const columns = columnsRes.ok ? await columnsRes.json() : [];
		
		const uniqueProcs = Array.from(new Set(columns.map((c: any) => c.process))) as string[];
		const initialProcess = uniqueProcs.length > 0 ? uniqueProcs[0] : '';
		
		// 2. Fetch registered devices
		const devicesRes = await fetch(dashboardApiUrl('/api/v1/devices'));
		const registeredDevices = devicesRes.ok ? await devicesRes.json() : [];

		// 3. Fetch registered alarm configurations
		const alarmsRes = await fetch(dashboardApiUrl('/api/v1/alarms'));
		const registeredAlarms = alarmsRes.ok ? await alarmsRes.json() : [];

		return {
			processes: uniqueProcs,
			initialProcess,
			registeredDevices,
			alarms: registeredAlarms
		};
	} catch (err) {
		console.error('Error in alarm-status server load:', err);
		return {
			processes: [],
			initialProcess: '',
			registeredDevices: [],
			alarms: []
		};
	}
};
