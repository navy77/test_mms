import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	try {
		const [usersRes, devicesRes, columnsRes, projectsRes, statusesRes, alarmsRes] = await Promise.all([
			fetch('http://localhost:8001/api/v1/users'),
			fetch('http://localhost:8001/api/v1/devices'),
			fetch('http://localhost:8001/api/v1/columns'),
			fetch('http://localhost:8001/api/v1/projects'),
			fetch('http://localhost:8001/api/v1/statuses'),
			fetch('http://localhost:8001/api/v1/alarms') 
		]);

		const users = usersRes.ok ? await usersRes.json() : [];
		const devices = devicesRes.ok ? await devicesRes.json() : [];
		const columns = columnsRes.ok ? await columnsRes.json() : [];
		const projects = projectsRes.ok ? await projectsRes.json() : [];
		const statuses = statusesRes.ok ? await statusesRes.json() : [];
		const alarms = alarmsRes.ok ? await alarmsRes.json() : [];

		return {
			users,
			devices,
			columns,
			projects,
			statuses,
			alarms
		};
	} catch (err) {
		console.error('Error loading data in setting server load:', err);
		return {
			users: [],
			devices: [],
			columns: [],
			projects: [],
			statuses: [],
			alarms: []
		};
	}
};
