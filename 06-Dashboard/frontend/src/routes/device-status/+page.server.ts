import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	try {
		// 1. Fetch columns to extract unique processes
		const columnsRes = await fetch('http://localhost:8001/api/v1/columns');
		const columns = columnsRes.ok ? await columnsRes.json() : [];
		
		const uniqueProcs = Array.from(new Set(columns.map((c: any) => c.process))) as string[];
		const initialProcess = uniqueProcs.length > 0 ? uniqueProcs[0] : '';
		
		// 2. Fetch initial status counts if we have a process
		let initialCounts = { total: 0, online: 0, offline: 0, communication_fail: 0 };
		if (initialProcess) {
			try {
				const countsRes = await fetch(`http://localhost:8003/api/v1/device/currently/status/${initialProcess}`);
				if (countsRes.ok) {
					const data = await countsRes.json();
					initialCounts = {
						total: data.total,
						online: data.online,
						offline: data.offline,
						communication_fail: data.communication_fail
					};
				}
			} catch (countsErr) {
				console.error('Error fetching initial status counts on server:', countsErr);
			}
		}

		// 3. Fetch registered devices
		const devicesRes = await fetch('http://localhost:8001/api/v1/devices');
		const registeredDevices = devicesRes.ok ? await devicesRes.json() : [];

		return {
			processes: uniqueProcs,
			initialProcess,
			initialCounts,
			registeredDevices
		};
	} catch (err) {
		console.error('Error in device-status server load:', err);
		return {
			processes: [],
			initialProcess: '',
			initialCounts: { total: 0, online: 0, offline: 0, communication_fail: 0 },
			registeredDevices: []
		};
	}
};
