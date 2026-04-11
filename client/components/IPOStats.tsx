import React, { useMemo } from 'react';
import { IPO } from '@/lib/types';

interface IPOStatsProps {
  ipos: IPO[];
  loading: boolean;
}

function getWeekStart(date: Date): string {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  d.setDate(diff);
  return d.toISOString().slice(0, 10);
}

function getNext8Weeks(): string[] {
  const weeks: string[] = [];
  const now = new Date();
  for (let i = 0; i < 8; i++) {
    const d = new Date(now);
    d.setDate(d.getDate() + i * 7);
    weeks.push(getWeekStart(d));
  }
  return weeks;
}

function formatTotalValue(total: number): string {
  if (total >= 1_000_000_000) return `$${(total / 1_000_000_000).toFixed(1)}B`;
  if (total >= 1_000_000) return `$${(total / 1_000_000).toFixed(1)}M`;
  if (total >= 1_000) return `$${(total / 1_000).toFixed(1)}K`;
  return `$${total.toLocaleString()}`;
}

function Sparkline({
  data,
  color,
  gradientId,
}: {
  data: number[];
  color: string;
  gradientId: string;
}) {
  if (data.length < 2) return <div className="w-20 h-9" />;

  const width = 80;
  const height = 36;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;

  const coords = data.map((val, i) => ({
    x: (i / (data.length - 1)) * width,
    y: height - ((val - min) / range) * (height - 6) - 3,
  }));

  const linePath = coords.reduce((path, p, i) => {
    if (i === 0) return `M${p.x.toFixed(1)},${p.y.toFixed(1)}`;
    const prev = coords[i - 1];
    const cpX = ((prev.x + p.x) / 2).toFixed(1);
    return `${path} C${cpX},${prev.y.toFixed(1)} ${cpX},${p.y.toFixed(1)} ${p.x.toFixed(1)},${p.y.toFixed(1)}`;
  }, '');

  const areaPath = `${linePath} L${width},${height} L0,${height} Z`;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="overflow-visible flex-shrink-0"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${gradientId})`} />
      <path
        d={linePath}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IPOStats({ ipos, loading }: IPOStatsProps) {
  const stats = useMemo(() => {
    if (loading || ipos.length === 0) return null;

    const today = new Date().toISOString().slice(0, 10);
    const weeks = getNext8Weeks();
    const thisWeekKey = weeks[0];
    const nextWeekKey = weeks[1];

    const countByWeek: Record<string, number> = {};
    const valueByWeek: Record<string, number> = {};
    weeks.forEach((w: string) => {
      countByWeek[w] = 0;
      valueByWeek[w] = 0;
    });

    const nextWeekStart = nextWeekKey;

    let scheduledToday = 0;
    let upcomingThisWeek = 0;
    let totalRaise = 0;

    ipos.forEach((ipo) => {
      const dateStr = ipo.estimatedIpoDate?.slice(0, 10);

      if (dateStr === today) scheduledToday++;
      if (dateStr && dateStr >= thisWeekKey && dateStr < nextWeekStart) upcomingThisWeek++;

      if (dateStr) {
        const weekKey = getWeekStart(new Date(dateStr));
        if (weekKey in countByWeek) countByWeek[weekKey]++;
      }

      if (ipo.raiseAmount) {
        const val = parseInt(ipo.raiseAmount.replace(/,/g, ''));
        if (!isNaN(val)) {
          totalRaise += val;
          if (ipo.estimatedIpoDate) {
            const weekKey = getWeekStart(new Date(ipo.estimatedIpoDate));
            if (weekKey in valueByWeek) valueByWeek[weekKey] += val;
          }
        }
      }
    });

    const thisWeekCount = countByWeek[thisWeekKey];
    const nextWeekCount = countByWeek[nextWeekKey];
    const weekChangePct =
      thisWeekCount > 0
        ? ((nextWeekCount - thisWeekCount) / thisWeekCount) * 100
        : null;

    return {
      totalIPOs: ipos.length,
      scheduledToday,
      upcomingThisWeek,
      totalValue: totalRaise > 0 ? formatTotalValue(totalRaise) : 'N/A',
      thisWeekValue: valueByWeek[thisWeekKey] > 0 ? formatTotalValue(valueByWeek[thisWeekKey]) : null,
      weekChangePct: weekChangePct !== null ? weekChangePct.toFixed(1) : null,
      weekChangePositive: weekChangePct === null || weekChangePct >= 0,
      ipoCountSparkline: weeks.map((w: string) => countByWeek[w]),
      valueSparkline: weeks.map((w: string) => valueByWeek[w]),
    };
  }, [ipos, loading]);

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {[...Array(3)].map((_, i) => (
          <div
            key={i}
            className="bg-white dark:bg-[#161b27] rounded-xl border border-gray-200 dark:border-[#252f3e] p-5 animate-pulse"
          >
            <div className="flex justify-between mb-4">
              <div className="h-4 bg-slate-100 rounded w-24" />
              <div className="h-4 w-4 bg-slate-100 rounded" />
            </div>
            <div className="flex items-end justify-between">
              <div>
                <div className="h-8 bg-slate-200 rounded w-16 mb-2" />
                <div className="h-3 bg-slate-100 rounded w-28" />
              </div>
              <div className="w-20 h-9 bg-slate-100 rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      {/* Active IPOs */}
      <div className="bg-white dark:bg-[#161b27] rounded-xl border border-gray-200 dark:border-[#252f3e] p-5 transition-all duration-300">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Active IPOs</p>
          <button className="text-slate-300 dark:text-slate-600 hover:text-slate-500 dark:hover:text-slate-400 transition-colors font-bold tracking-widest text-sm">
            ···
          </button>
        </div>
        <div className="flex items-end justify-between gap-2">
          <div>
            <p className="text-3xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">{stats.totalIPOs}</p>
            {stats.weekChangePct !== null ? (
              <p className={`text-xs font-medium mt-1 ${stats.weekChangePositive ? 'text-emerald-500' : 'text-red-400'}`}>
                {stats.weekChangePositive ? '+' : ''}{stats.weekChangePct}% this week
              </p>
            ) : (
              <p className="text-xs font-medium mt-1 text-slate-400">No prior week data</p>
            )}
          </div>
          <Sparkline data={stats.ipoCountSparkline} color="#3b82f6" gradientId="grad-ipo" />
        </div>
      </div>

      {/* Scheduled Today */}
      <div className="bg-white dark:bg-[#161b27] rounded-xl border border-gray-200 dark:border-[#252f3e] p-5 transition-all duration-300">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Scheduled Today</p>
          <button className="text-slate-300 dark:text-slate-600 hover:text-slate-500 dark:hover:text-slate-400 transition-colors font-bold tracking-widest text-sm">
            ···
          </button>
        </div>
        <div className="flex items-end justify-between gap-2">
          <div>
            <p className="text-3xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">{stats.scheduledToday}</p>
            <p className="text-xs font-medium mt-1 text-slate-400">
              {stats.upcomingThisWeek} upcoming this week
            </p>
          </div>
          <Sparkline data={stats.ipoCountSparkline} color="#10b981" gradientId="grad-today" />
        </div>
      </div>

      {/* Total Value */}
      <div className="bg-white dark:bg-[#161b27] rounded-xl border border-gray-200 dark:border-[#252f3e] p-5 transition-all duration-300">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Total Value</p>
          <button className="text-slate-300 dark:text-slate-600 hover:text-slate-500 dark:hover:text-slate-400 transition-colors font-bold tracking-widest text-sm">
            ···
          </button>
        </div>
        <div className="flex items-end justify-between gap-2">
          <div>
            <p className="text-3xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">{stats.totalValue}</p>
            <p className="text-xs font-medium mt-1 text-emerald-500">
              {stats.thisWeekValue ? `${stats.thisWeekValue} this week` : <span className="text-slate-400">No data this week</span>}
            </p>
          </div>
          <Sparkline data={stats.valueSparkline} color="#10b981" gradientId="grad-value" />
        </div>
      </div>
    </div>
  );
}
