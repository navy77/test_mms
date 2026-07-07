// Simple client-side session store using Svelte 5 runes
// Stores auth state in memory + sessionStorage for page refresh persistence

export interface AuthUser {
	username: string;
	role: 'admin' | 'user';
}

function createAuthStore() {
	// Try to restore from sessionStorage on init
	const stored = typeof sessionStorage !== 'undefined'
		? sessionStorage.getItem('mms_auth')
		: null;

	let user = $state<AuthUser | null>(stored ? JSON.parse(stored) : null);

	return {
		get user() { return user; },
		get isLoggedIn() { return user !== null; },
		get isAdmin() { return user?.role === 'admin'; },

		login(u: AuthUser) {
			user = u;
			if (typeof sessionStorage !== 'undefined') {
				sessionStorage.setItem('mms_auth', JSON.stringify(u));
			}
		},
		logout() {
			user = null;
			if (typeof sessionStorage !== 'undefined') {
				sessionStorage.removeItem('mms_auth');
			}
		}
	};
}

export const auth = createAuthStore();
