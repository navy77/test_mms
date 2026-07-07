import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	try {
		const [usersRes, devicesRes, columnsRes] = await Promise.all([
			fetch('http://localhost:8001/api/users'),
			fetch('http://localhost:8001/api/devices'),
			fetch('http://localhost:8001/api/columns')
		]);

		const users = usersRes.ok ? await usersRes.json() : [];
		const devices = devicesRes.ok ? await devicesRes.json() : [];
		const columns = columnsRes.ok ? await columnsRes.json() : [];

		return {
			users,
			devices,
			columns
		};
	} catch (err) {
		console.error('Error loading data in setting server load:', err);
		return {
			users: [],
			devices: [],
			columns: []
		};
	}
};
