<script lang="ts">
	import { dashboardApiUrl } from '$lib/api';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { Activity, Loader2, Eye, EyeOff } from '@lucide/svelte';
	import { fade, fly } from 'svelte/transition';
	import { onMount } from 'svelte';

	let username = $state('');
	let password = $state('');
	let errorMsg = $state('');
	let loading = $state(false);
	let showPassword = $state(false);
	
	// Canvas reference
	let canvasElement = $state<HTMLCanvasElement | null>(null);

	onMount(() => {
		if (!canvasElement) return;
		const ctx = canvasElement.getContext('2d');
		if (!ctx) return;

		let animationFrameId: number;
		let width = (canvasElement.width = window.innerWidth);
		let height = (canvasElement.height = window.innerHeight);

		const handleResize = () => {
			if (!canvasElement) return;
			width = canvasElement.width = window.innerWidth;
			height = canvasElement.height = window.innerHeight;
			generateCircuit();
		};
		window.addEventListener('resize', handleResize);

		// Grid & Circuit Track Setup
		const gridSize = 100;
		interface Point { x: number; y: number; }
		interface Track { points: Point[]; }
		interface Pulse {
			trackIndex: number;
			pointIndex: number; // Index of the point it is moving towards
			x: number;
			y: number;
			speed: number;
			progress: number; // 0 to 1 along the current segment
		}

		let tracks: Track[] = [];
		let pulses: Pulse[] = [];
		let mouse = { x: -1000, y: -1000 };

		// Generate random PCB routes
		function generateCircuit() {
			tracks = [];
			pulses = [];
			const cols = Math.ceil(width / gridSize) + 1;
			const rows = Math.ceil(height / gridSize) + 1;

			// Generate 40 random PCB tracks
			const numTracks = 45;
			for (let t = 0; t < numTracks; t++) {
				const points: Point[] = [];
				// Pick random starting grid cell
				let c = Math.floor(Math.random() * cols);
				let r = Math.floor(Math.random() * rows);
				
				let x = c * gridSize;
				let y = r * gridSize;
				points.push({ x, y });

				const steps = Math.floor(Math.random() * 4) + 3; // 3 to 6 segments per track
				let lastDir = -1;

				for (let s = 0; s < steps; s++) {
					// 45 and 90-degree PCB directions
					const dirs = [
						{ dx: 1, dy: 0 },   // East
						{ dx: 0, dy: 1 },   // South
						{ dx: -1, dy: 0 },  // West
						{ dx: 0, dy: -1 },  // North
						{ dx: 1, dy: 1 },   // South-East
						{ dx: -1, dy: 1 },  // South-West
						{ dx: 1, dy: -1 },  // North-East
						{ dx: -1, dy: -1 }  // North-West
					];

					// Filter directions to avoid 180-degree immediate backtrack
					const allowedDirs = dirs.filter((_, idx) => {
						if (lastDir === -1) return true;
						// Opposites indices: (0,2), (1,3), (4,7), (5,6)
						if (lastDir === 0 && idx === 2) return false;
						if (lastDir === 2 && idx === 0) return false;
						if (lastDir === 1 && idx === 3) return false;
						if (lastDir === 3 && idx === 1) return false;
						if (lastDir === 4 && idx === 7) return false;
						if (lastDir === 7 && idx === 4) return false;
						if (lastDir === 5 && idx === 6) return false;
						if (lastDir === 6 && idx === 5) return false;
						return true;
					});

					const dir = allowedDirs[Math.floor(Math.random() * allowedDirs.length)];
					const length = (Math.floor(Math.random() * 2) + 1) * gridSize;
					
					x += dir.dx * length;
					y += dir.dy * length;

					// Clamp within bounds
					x = Math.max(0, Math.min(width, x));
					y = Math.max(0, Math.min(height, y));

					points.push({ x, y });
				}
				tracks.push({ points });
			}

			// Seed 15 initial random pulses
			for (let i = 0; i < 15; i++) {
				spawnRandomPulse();
			}
		}

		function spawnRandomPulse() {
			if (tracks.length === 0) return;
			const idx = Math.floor(Math.random() * tracks.length);
			const track = tracks[idx];
			if (track.points.length < 2) return;

			pulses.push({
				trackIndex: idx,
				pointIndex: 1,
				x: track.points[0].x,
				y: track.points[0].y,
				speed: Math.random() * 1.5 + 1.2,
				progress: 0
			});
		}

		// Mouse listeners
		const handleMouseMove = (e: MouseEvent) => {
			mouse.x = e.clientX;
			mouse.y = e.clientY;

			// Spawn a pulse on the closest track segment on mouse move (throttled)
			if (Math.random() < 0.12 && tracks.length > 0) {
				// Find closest track node to mouse
				let closestTrackIndex = -1;
				let minDistance = 150;

				for (let i = 0; i < tracks.length; i++) {
					const startPt = tracks[i].points[0];
					const d = Math.hypot(startPt.x - mouse.x, startPt.y - mouse.y);
					if (d < minDistance) {
						minDistance = d;
						closestTrackIndex = i;
					}
				}

				if (closestTrackIndex !== -1) {
					// Spawn pulse at start of this track
					pulses.push({
						trackIndex: closestTrackIndex,
						pointIndex: 1,
						x: tracks[closestTrackIndex].points[0].x,
						y: tracks[closestTrackIndex].points[0].y,
						speed: 2.2, // Faster pulse for interactive feedback
						progress: 0
					});
				}
			}
		};

		const handleMouseLeave = () => {
			mouse.x = -1000;
			mouse.y = -1000;
		};

		window.addEventListener('mousemove', handleMouseMove);
		window.addEventListener('mouseleave', handleMouseLeave);

		generateCircuit();

		// Animation Frame
		const draw = () => {
			if (!ctx) return;
			ctx.clearRect(0, 0, width, height);

			// 1. Draw static PCB grid background (dots)
			ctx.fillStyle = 'rgba(255, 255, 255, 0.015)';
			const cols = Math.ceil(width / gridSize) + 1;
			const rows = Math.ceil(height / gridSize) + 1;
			for (let c = 0; c < cols; c++) {
				for (let r = 0; r < rows; r++) {
					ctx.beginPath();
					ctx.arc(c * gridSize, r * gridSize, 1, 0, Math.PI * 2);
					ctx.fill();
				}
			}

			// 2. Draw tracks (lines)
			tracks.forEach((track) => {
				ctx.beginPath();
				ctx.moveTo(track.points[0].x, track.points[0].y);
				for (let i = 1; i < track.points.length; i++) {
					ctx.lineTo(track.points[i].x, track.points[i].y);
				}

				// Check proximity to mouse to light up circuit track slightly
				let isNearMouse = false;
				for (let i = 0; i < track.points.length; i++) {
					if (Math.hypot(track.points[i].x - mouse.x, track.points[i].y - mouse.y) < 180) {
						isNearMouse = true;
						break;
					}
				}

				ctx.strokeStyle = isNearMouse ? 'rgba(59, 130, 246, 0.16)' : 'rgba(59, 130, 246, 0.05)';
				ctx.lineWidth = 1.2;
				ctx.stroke();

				// Draw node pads (dots at joints)
				track.points.forEach((pt) => {
					ctx.beginPath();
					ctx.arc(pt.x, pt.y, 2, 0, Math.PI * 2);
					ctx.fillStyle = isNearMouse ? 'rgba(59, 130, 246, 0.28)' : 'rgba(59, 130, 246, 0.1)';
					ctx.fill();
				});
			});

			// 3. Update and draw pulses
			for (let i = pulses.length - 1; i >= 0; i--) {
				const pulse = pulses[i];
				const track = tracks[pulse.trackIndex];
				const start = track.points[pulse.pointIndex - 1];
				const end = track.points[pulse.pointIndex];

				// Move pulse along segment
				const segmentLength = Math.hypot(end.x - start.x, end.y - start.y);
				pulse.progress += pulse.speed / segmentLength;

				if (pulse.progress >= 1) {
					// Move to next segment
					pulse.pointIndex++;
					pulse.progress = 0;

					if (pulse.pointIndex >= track.points.length) {
						// End of track reached, remove and spawn a new random one
						pulses.splice(i, 1);
						spawnRandomPulse();
						continue;
					}
				}

				// Calculate actual coordinates
				const currStart = track.points[pulse.pointIndex - 1];
				const currEnd = track.points[pulse.pointIndex];
				pulse.x = currStart.x + (currEnd.x - currStart.x) * pulse.progress;
				pulse.y = currStart.y + (currEnd.y - currStart.y) * pulse.progress;

				// Draw glowing pulse dot
				ctx.beginPath();
				ctx.arc(pulse.x, pulse.y, 3, 0, Math.PI * 2);
				ctx.fillStyle = 'rgba(59, 130, 246, 0.95)'; // Glowing blue
				ctx.shadowColor = 'rgba(59, 130, 246, 0.8)';
				ctx.shadowBlur = 8;
				ctx.fill();
				
				// Reset shadow blur for other drawings
				ctx.shadowBlur = 0;

				// Draw slight tail
				ctx.beginPath();
				ctx.arc(pulse.x - (currEnd.x - currStart.x) * 0.05, pulse.y - (currEnd.y - currStart.y) * 0.05, 2, 0, Math.PI * 2);
				ctx.fillStyle = 'rgba(59, 130, 246, 0.4)';
				ctx.fill();
			}

			animationFrameId = requestAnimationFrame(draw);
		};

		draw();

		return () => {
			cancelAnimationFrame(animationFrameId);
			window.removeEventListener('resize', handleResize);
			window.removeEventListener('mousemove', handleMouseMove);
			window.removeEventListener('mouseleave', handleMouseLeave);
		};
	});

	async function handleLogin(e: SubmitEvent) {
		e.preventDefault();
		if (!username || !password) {
			errorMsg = 'Please fill in both fields.';
			return;
		}

		errorMsg = '';
		loading = true;

		try {
			const res = await fetch(dashboardApiUrl('/auth/login'), {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({ username, password })
			});

			if (!res.ok) {
				const errorData = await res.json();
				throw new Error(errorData.detail || 'Login failed');
			}

			const data = await res.json();
			if (data.success) {
				 auth.login({
					username: data.username,
					role: data.role,
					accessToken: data.access_token
				});
				goto('/');
			} else {
				throw new Error('Authentication failed');
			}
		} catch (err: unknown) {
			errorMsg = err instanceof Error ? err.message : 'Connection failed. Please try again.';
		} finally {
			loading = false;
		}
	}
</script>

<div class="relative flex min-h-screen items-center justify-center bg-background px-4 overflow-hidden select-none">
	
	<!-- Smart Circuit Board (PCB) Canvas Background -->
	<canvas bind:this={canvasElement} class="absolute inset-0 w-full h-full pointer-events-none z-0"></canvas>

	<!-- Interactive Light Glow behind Card -->
	<div class="absolute w-[350px] h-[350px] bg-primary/10 rounded-full blur-[100px] pointer-events-none z-0"></div>

	<!-- Glassmorphism Login Card -->
	<div
		in:fly={{ y: 40, duration: 800 }}
		class="w-full max-w-sm rounded-xl border border-white/10 dark:border-white/5 bg-card/60 backdrop-blur-xl p-6 shadow-2xl transition-all duration-300 z-10 hover:border-primary/30"
	>
		<div class="mb-6 text-center">
			<div class="flex justify-center mb-4">
				{#if loading}
					<div class="inline-flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
						<Loader2 class="h-6 w-6 text-primary animate-spin" />
					</div>
				{:else}
					<img src="/img/nmb.png" alt="NMB Logo" class="h-10 w-auto object-contain mix-blend-multiply dark:mix-blend-normal dark:invert dark:hue-rotate-180" />
				{/if}
			</div>
			<h2 class="mt-3 text-lg font-semibold text-card-foreground">MMS Monitor Login</h2>
			<p class="text-xs text-muted-foreground">Sign in to access your IoT Dashboard</p>
		</div>

		{#if errorMsg}
			<div
				transition:fade={{ duration: 300 }}
				class="mb-4 rounded-md bg-destructive/10 p-3 text-xs font-medium text-destructive border border-destructive/20"
			>
				{errorMsg}
			</div>
		{/if}

		<form onsubmit={handleLogin} class="space-y-4">
			<div>
				<label for="username" class="mb-1.5 block text-xs font-medium text-muted-foreground">Username</label>
				<input
					id="username"
					bind:value={username}
					type="text"
					class="w-full rounded-md border border-border bg-background/50 px-3 py-2 text-sm text-foreground outline-none focus:border-primary transition-colors"
					placeholder="Enter username"
					required
					disabled={loading}
				/>
			</div>

			<div>
				<label for="password" class="mb-1.5 block text-xs font-medium text-muted-foreground">Password</label>
				<div class="relative">
					<input
						id="password"
						bind:value={password}
						type={showPassword ? 'text' : 'password'}
						class="w-full rounded-md border border-border bg-background/50 pl-3 pr-10 py-2 text-sm text-foreground outline-none focus:border-primary transition-colors"
						placeholder="Enter password"
						required
						disabled={loading}
					/>
					
					<!-- Interactive eye button -->
					<button
						type="button"
						class="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors outline-none"
						onclick={() => (showPassword = !showPassword)}
						tabindex="-1"
					>
						{#if showPassword}
							<EyeOff class="h-4 w-4" />
						{:else}
							<Eye class="h-4 w-4" />
						{/if}
					</button>
				</div>
			</div>

			<button
				type="submit"
				class="w-full rounded-md bg-primary hover:bg-primary/90 py-2 text-sm font-semibold text-white transition-all disabled:opacity-50 shadow-md shadow-primary/20 active:scale-[0.98]"
				disabled={loading}
			>
				{loading ? 'Authenticating...' : 'Sign In'}
			</button>
		</form>

		<!-- Footer Meta Info -->
		<div class="mt-6 flex flex-col items-right justify-right gap-0.5 text-[10px] text-muted-foreground font-semibold">
			<span>Version 1.0.0</span>
			<span class="opacity-75">Powered by MIC Division Thailand</span>
		</div>
	</div>
</div>
