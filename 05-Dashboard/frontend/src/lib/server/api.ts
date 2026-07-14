import { env } from '$env/dynamic/private';

const DEFAULT_DASHBOARD_API_INTERNAL = 'http://localhost:8001';

function trimTrailingSlash(value: string): string {
	return value.replace(/\/+$/, '');
}

export function dashboardApiUrl(path: string): string {
	const origin = trimTrailingSlash(env.DASHBOARD_API_INTERNAL || DEFAULT_DASHBOARD_API_INTERNAL);
	return `${origin}${path.startsWith('/') ? path : `/${path}`}`;
}
