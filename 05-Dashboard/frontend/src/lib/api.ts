import { env } from '$env/dynamic/public';
import { browser } from '$app/environment';

const DEFAULT_DASHBOARD_API_ORIGIN = 'http://localhost:8001';
const DEFAULT_HISTORY_API_ORIGIN = 'http://localhost:8003';

function trimTrailingSlash(value: string): string {
	return value.replace(/\/+$/, '');
}

export function dashboardApiUrl(path: string): string {
	let origin = env.PUBLIC_DASHBOARD_API_ORIGIN;
	if (!origin && browser && window.location.hostname) {
		origin = `http://${window.location.hostname}:8001`;
	}
	origin = trimTrailingSlash(origin || DEFAULT_DASHBOARD_API_ORIGIN);
	return `${origin}${path.startsWith('/') ? path : `/${path}`}`;
}

export function historyApiUrl(path: string): string {
	let origin = env.PUBLIC_HISTORY_API_ORIGIN;
	if (!origin && browser && window.location.hostname) {
		origin = `http://${window.location.hostname}:8003`;
	}
	origin = trimTrailingSlash(origin || DEFAULT_HISTORY_API_ORIGIN);
	return `${origin}${path.startsWith('/') ? path : `/${path}`}`;
}

