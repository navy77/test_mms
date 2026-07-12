import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	try {
		// 1. Fetch columns to extract unique processes
		const columnsRes = await fetch('http://localhost:8001/api/v1/columns');
		const columns = columnsRes.ok ? await columnsRes.json() : [];
		
		const uniqueProcs = Array.from(new Set(columns.map((c: any) => c.process))) as string[];
		const initialProcess = uniqueProcs.length > 0 ? uniqueProcs[0] : '';
		
		// 2. Fetch registered devices
		const devicesRes = await fetch('http://localhost:8001/api/v1/devices');
		const registeredDevices = devicesRes.ok ? await devicesRes.json() : [];

		// 3. Fetch registered statuses for colors
		const statusesRes = await fetch('http://localhost:8001/api/v1/statuses');
		const statuses = statusesRes.ok ? await statusesRes.json() : [];

		return {
			processes: uniqueProcs,
			initialProcess,
			registeredDevices,
			statuses
		};
	} catch (err) {
		console.error('Error in machine-status server load:', err);
		return {
			processes: [],
			initialProcess: '',
			registeredDevices: [],
			statuses: []
		};
	}
};
