import { dashboardApiUrl } from '$lib/server/api';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	try {
		const [usersRes, devicesRes, columnsRes, projectsRes, statusesRes, alarmsRes] = await Promise.all([
			fetch(dashboardApiUrl('/api/v1/users')),
			fetch(dashboardApiUrl('/api/v1/devices')),
			fetch(dashboardApiUrl('/api/v1/columns')),
			fetch(dashboardApiUrl('/api/v1/projects')),
			fetch(dashboardApiUrl('/api/v1/statuses')),
			fetch(dashboardApiUrl('/api/v1/alarms')) 
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
