import { dashboardApiUrl } from '$lib/server/api';
import type { PageServerLoad } from "./$types";

interface LoadData {
	processes: string[];
	initialProcess: string;
	registeredDevices: any[];
}

export const load: PageServerLoad = async ({ fetch }): Promise<LoadData> => {
	try {
		const columnsRes = await fetch(dashboardApiUrl('/api/v1/columns'));
		const columns = columnsRes.ok ? await columnsRes.json() : [];

		const uniqueProcs = Array.from(new Set(columns.map((c: any) => c.process))) as string[];
		const initialProcess = uniqueProcs.length > 0 ? uniqueProcs[0] : "";

		const devicesRes = await fetch(dashboardApiUrl('/api/v1/devices'));
		const registeredDevices = devicesRes.ok ? await devicesRes.json() : [];

		return {
			processes: uniqueProcs,
			initialProcess,
			registeredDevices
		};
	} catch (err) {
		console.error("Error in device-status-utl-daily server load:", err);
		return {
			processes: [],
			initialProcess: "",
			registeredDevices: []
		};
	}
};
