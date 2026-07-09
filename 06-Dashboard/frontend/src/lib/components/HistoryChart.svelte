<script lang="ts">
	import { onMount, onDestroy } from "svelte";
	import { LoaderCircle, AlertCircle } from "lucide-svelte";

	interface StatusSegment {
		status: string;
		duration: number;
		ratio: number;
	}

	interface DailyRecord {
		date: string;
		device: string;
		data: StatusSegment[];
		utilize: number;
	}

	interface Props {
		process: string;
		device: string;
		colorMap: Record<string, string>;
	}

	let { process, device, colorMap }: Props = $props();

	let chartEl = $state<HTMLElement | null>(null);
	let chartInstance: any = null;
	let ApexChartsClass = $state<any>(null);

	let dailyRecords = $state<DailyRecord[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	async function fetchData(p: string, d: string) {
		loading = true;
		error = null;
		dailyRecords = [];

		try {
			const res = await fetch(`http://localhost:8003/api/v1/status/daily/${p}/${d}`);
			if (!res.ok) {
				error = `No data (${res.status})`;
				loading = false;
				return;
			}
			const json = await res.json();
			dailyRecords = Array.isArray(json) ? json : [];
			loading = false;
		} catch (e) {
			error = "Fetch error";
			loading = false;
		}
	}

	$effect(() => {
		if (process && device) {
			fetchData(process, device);
		}
	});

	onMount(async () => {
		const module = await import("apexcharts");
		ApexChartsClass = module.default;
	});

	$effect(() => {
		if (!chartEl || !ApexChartsClass || dailyRecords.length === 0) return;

		// All unique statuses — include 'no data' so full bar is shown on empty days
		const priorityOrder = ["run", "alarm", "wait", "stop", "other", "offline", "no data"];
		const rawStatuses = Array.from(
			new Set(dailyRecords.flatMap((d) => d.data.map((s) => s.status)))
		);
		const allStatuses = [
			...priorityOrder.filter((s) => rawStatuses.includes(s)),
			...rawStatuses.filter((s) => !priorityOrder.includes(s))
		];

		// Date labels
		const categories = dailyRecords.map((r) => {
			const d = new Date(r.date + "T00:00:00");
			return d.getDate();
		});

		// Stacked bar series — ratio is already in % (e.g. 82.9 = 82.9%)
		const stackedSeries = allStatuses.map((status) => ({
			name: status === "no data" ? "No Data" : status.charAt(0).toUpperCase() + status.slice(1),
			type: "bar",
			color: colorMap[status] || "#374151",
			data: dailyRecords.map((r) => {
				const seg = r.data.find((s) => s.status === status);
				return seg ? Math.round(seg.ratio * 10) / 10 : 0;
			})
		}));

		// Utilize % line — utilize is already in % (e.g. 29.9 = 29.9%)
		const utilizeSeries = {
			name: "Utilize %",
			type: "line",
			color: "#f472b6",
			data: dailyRecords.map((r) => Math.round(r.utilize * 10) / 10)
		};

		const series = [...stackedSeries, utilizeSeries];

		const options = {
			chart: {
				type: "bar",
				height: 200,
				stacked: true,
				stackType: "normal",
				toolbar: { show: false },
				animations: { enabled: false },
				zoom: { enabled: false },
				background: "transparent",
				sparkline: { enabled: false }
			},
			plotOptions: {
				bar: {
					columnWidth: "90%",
					borderRadius: 0
				}
			},
			stroke: {
				width: series.map((s: any) => (s.type === "line" ? 2.5 : 0)),
				curve: "smooth"
			},
			markers: {
				size: series.map((s: any) => (s.type === "line" ? 0 : 0)),
				hover: { size: 4 }
			},
			series,
			xaxis: {
				categories,
				labels: {
					style: { colors: "#6b7280", fontSize: "9px" },
					rotate: 0
				},
				axisBorder: { show: false },
				axisTicks: { show: false }
			},
			yaxis: [
				{
					min: 0,
					max: 100,
					tickAmount: 4,
					labels: {
						formatter: (v: number) => `${v}%`,
						style: { colors: "#6b7280", fontSize: "9px" }
					}
				}
			],
			annotations: {},
			legend: { show: false },
			grid: {
				borderColor: "rgba(255,255,255,0.06)",
				strokeDashArray: 3,
				padding: { top: -6, right: 10, bottom: 0, left: 0 }
			},
			tooltip: {
				shared: true,
				intersect: false,
				theme: "dark",
				y: {
					formatter: (v: number, opts: any) => {
						if (opts?.seriesIndex === series.length - 1) return `${v}%`;
						return `${v}%`;
					}
				}
			},
			theme: { mode: "dark" },
			dataLabels: { enabled: false },
			fill: {
				opacity: series.map((s: any) => (s.type === "line" ? 1 : 0.92))
			}
		};

		if (chartInstance) {
			chartInstance.destroy();
		}
		chartInstance = new ApexChartsClass(chartEl, options);
		chartInstance.render();
	});

	onDestroy(() => {
		if (chartInstance) chartInstance.destroy();
	});
</script>

<div class="w-full relative" style="height: 200px">
	{#if loading}
		<div class="absolute inset-0 flex items-center justify-center z-10">
			<LoaderCircle class="h-4 w-4 animate-spin text-muted-foreground" />
		</div>
	{:else if error}
		<div class="absolute inset-0 flex items-center justify-center gap-1.5 text-muted-foreground z-10">
			<AlertCircle class="h-3.5 w-3.5" />
			<span class="text-[10px]">{error}</span>
		</div>
	{/if}
	<div bind:this={chartEl} class="w-full h-full"></div>
</div>
