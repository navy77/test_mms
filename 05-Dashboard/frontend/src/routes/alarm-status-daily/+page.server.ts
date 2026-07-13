import type { PageServerLoad } from './$types';

interface LoadData {
	processes: string[];
	initialProcess: string;
	registeredDevices: any[];
	alarms: any[];
}

export const load: PageServerLoad = async ({ fetch }): Promise<LoadData> => {
	try {
		const columnsRes = await fetch('http://localhost:8001/api/v1/columns');
		const columns = columnsRes.ok ? await columnsRes.json() : [];

		const processes = Array.from(new Set(columns.map((c: any) => c.process))) as string[];
		const initialProcess = processes[0] || '';

		const devicesRes = await fetch('http://localhost:8001/api/v1/devices');
		const registeredDevices = devicesRes.ok ? await devicesRes.json() : [];

		const alarmsRes = await fetch('http://localhost:8001/api/v1/alarms');
		const alarms = alarmsRes.ok ? await alarmsRes.json() : [];

		return {
			processes,
			initialProcess,
			registeredDevices,
			alarms
		};
	} catch (err) {
		console.error('Error in alarm-status-daily server load:', err);
		return {
			processes: [],
			initialProcess: '',
			registeredDevices: [],
			alarms: []
		};
	}
};
