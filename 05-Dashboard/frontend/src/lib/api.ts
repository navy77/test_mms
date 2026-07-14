import { env } from '$env/dynamic/public';

const DEFAULT_DASHBOARD_API_ORIGIN = 'http://localhost:8001';
const DEFAULT_HISTORY_API_ORIGIN = 'http://localhost:8003';

function trimTrailingSlash(value: string): string {
	return value.replace(/\/+$/, '');
}

export function dashboardApiUrl(path: string): string {
	const origin = trimTrailingSlash(env.PUBLIC_DASHBOARD_API_ORIGIN || DEFAULT_DASHBOARD_API_ORIGIN);
	return `${origin}${path.startsWith('/') ? path : `/${path}`}`;
}

export function historyApiUrl(path: string): string {
	const origin = trimTrailingSlash(env.PUBLIC_HISTORY_API_ORIGIN || DEFAULT_HISTORY_API_ORIGIN);
	return `${origin}${path.startsWith('/') ? path : `/${path}`}`;
}
