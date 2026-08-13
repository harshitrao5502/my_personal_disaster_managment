'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  Calendar,
  CheckCircle2,
  Clock,
  Laptop,
  Phone,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from 'lucide-react';

interface CallRecord {
  call_id: string;
  started_at: string;
  ended_at: string | null;
  outcome: 'success' | 'failed';
  channel: 'browser' | 'sip';
}

interface StatsData {
  total_calls: number;
  successful_calls: number;
  failed_calls: number;
  recent_calls: CallRecord[];
}

export default function Dashboard() {
  const [stats, setStats] = useState<StatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());

  const fetchStats = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true);
    try {
      const response = await fetch('http://localhost:8000/api/dashboard/stats');
      if (!response.ok) {
        throw new Error(`API returned HTTP status ${response.status}`);
      }
      const data = await response.json();
      if (data.error) {
        throw new Error(data.error);
      }
      setStats(data);
      setError(null);
      setLastRefreshed(new Date());
    } catch (err) {
      console.error('Error fetching statistics:', err);
      setError(
        'Failed to connect to the backend stats service. Please ensure the backend agent worker is running on your machine.'
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Poll statistics every 5 seconds
  useEffect(() => {
    fetchStats();
    const interval = setInterval(() => {
      fetchStats();
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  const formatDuration = (startStr: string, endStr: string | null) => {
    if (!endStr) return 'Ongoing';
    try {
      const start = new Date(startStr);
      const end = new Date(endStr);
      const diffMs = end.getTime() - start.getTime();
      const diffSecs = Math.max(0, Math.round(diffMs / 1000));
      const mins = Math.floor(diffSecs / 60);
      const secs = diffSecs % 60;
      return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
    } catch {
      return '--';
    }
  };

  const formatTimestamp = (isoStr: string) => {
    try {
      const date = new Date(isoStr);
      return (
        date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) +
        ' ' +
        date.toLocaleDateString([], { month: 'short', day: 'numeric' })
      );
    } catch {
      return isoStr;
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 p-6 font-sans text-slate-100 selection:bg-teal-500/30 md:p-12">
      <div className="mx-auto max-w-6xl space-y-8">
        {/* Header */}
        <header className="flex flex-col gap-4 border-b border-slate-800/80 pb-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <span className="relative flex h-3.5 w-3.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal-400 opacity-75"></span>
                <span className="relative inline-flex h-3.5 w-3.5 rounded-full bg-teal-500"></span>
              </span>
              <h1 className="bg-gradient-to-r from-teal-400 via-emerald-400 to-cyan-400 bg-clip-text text-2xl font-extrabold tracking-tight text-transparent md:text-3xl">
                Raksha Emergency Response Dashboard
              </h1>
            </div>
            <p className="text-sm font-medium text-slate-400">
              Real-time call analytics & system health tracker
            </p>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-xs text-slate-400 tabular-nums">
              Last updated: {lastRefreshed.toLocaleTimeString()}
            </span>
            <button
              onClick={() => fetchStats(true)}
              disabled={refreshing}
              className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-800 bg-slate-900 px-4 py-2 text-sm font-semibold transition-all hover:border-slate-700 hover:bg-slate-800 active:scale-95 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 text-teal-400 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </header>

        {/* Error Alert */}
        {error && (
          <div className="animate-in fade-in slide-in-from-top-2 flex items-start gap-3.5 rounded-xl border border-red-900/50 bg-red-950/20 p-4 text-red-200 backdrop-blur-md transition-all duration-300">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-red-300">Connection Error</h3>
              <p className="text-xs leading-relaxed text-red-200/80">{error}</p>
            </div>
          </div>
        )}

        {/* Metrics Grid */}
        <section className="grid grid-cols-1 gap-6 sm:grid-cols-3">
          {/* Card 1: Total Calls */}
          <div className="group relative overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-900/30 p-6 backdrop-blur-lg transition-all duration-300 hover:border-slate-700/80">
            <div className="absolute top-0 right-0 p-4 opacity-5 transition-opacity duration-300 group-hover:opacity-10">
              <Activity className="h-24 w-24 text-teal-400" />
            </div>
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-teal-500/10 p-2.5 text-teal-400">
                  <Activity className="h-5 w-5" />
                </div>
                <h2 className="text-sm font-bold tracking-wider text-slate-400 uppercase">
                  Total Calls
                </h2>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-black tracking-tight text-slate-100 tabular-nums transition-all duration-500 md:text-5xl">
                  {loading ? '---' : (stats?.total_calls ?? 0)}
                </span>
                <span className="text-xs font-medium text-slate-400">sessions</span>
              </div>
            </div>
          </div>

          {/* Card 2: Successful Calls */}
          <div className="group relative overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-900/30 p-6 backdrop-blur-lg transition-all duration-300 hover:border-slate-700/80">
            <div className="absolute top-0 right-0 p-4 opacity-5 transition-opacity duration-300 group-hover:opacity-10">
              <CheckCircle2 className="h-24 w-24 text-emerald-400" />
            </div>
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-emerald-500/10 p-2.5 text-emerald-400">
                  <CheckCircle2 className="h-5 w-5" />
                </div>
                <h2 className="text-sm font-bold tracking-wider text-slate-400 uppercase">
                  Successful Calls
                </h2>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-black tracking-tight text-emerald-400 tabular-nums transition-all duration-500 md:text-5xl">
                  {loading ? '---' : (stats?.successful_calls ?? 0)}
                </span>
                <span className="text-xs font-medium text-slate-400">
                  {stats && stats.total_calls > 0
                    ? `${Math.round((stats.successful_calls / stats.total_calls) * 100)}% rate`
                    : '0% rate'}
                </span>
              </div>
            </div>
          </div>

          {/* Card 3: Failed Calls */}
          <div className="group relative overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-900/30 p-6 backdrop-blur-lg transition-all duration-300 hover:border-slate-700/80">
            <div className="absolute top-0 right-0 p-4 opacity-5 transition-opacity duration-300 group-hover:opacity-10">
              <XCircle className="h-24 w-24 text-rose-400" />
            </div>
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-rose-500/10 p-2.5 text-rose-400">
                  <XCircle className="h-5 w-5" />
                </div>
                <h2 className="text-sm font-bold tracking-wider text-slate-400 uppercase">
                  Failed / Incomplete
                </h2>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-black tracking-tight text-rose-400 tabular-nums transition-all duration-500 md:text-5xl">
                  {loading ? '---' : (stats?.failed_calls ?? 0)}
                </span>
                <span className="text-xs font-medium text-slate-400">unresolved</span>
              </div>
            </div>
          </div>
        </section>

        {/* Live Call Auditing */}
        <section className="space-y-4 rounded-2xl border border-slate-800/80 bg-slate-900/20 p-6 backdrop-blur-md">
          <div className="border-slate-850 flex items-center justify-between border-b pb-4">
            <div className="space-y-0.5">
              <h2 className="text-lg font-bold text-slate-200">Recent Call Logs</h2>
              <p className="text-xs text-slate-500">
                Live logs for the last 10 incoming and outgoing sessions
              </p>
            </div>
            <span className="rounded-full border border-slate-700/60 bg-slate-800 px-2.5 py-1 text-xs font-semibold text-slate-300">
              Real-Time Feed
            </span>
          </div>

          <div className="overflow-x-auto">
            {loading ? (
              <div className="flex flex-col items-center justify-center gap-3 py-12">
                <RefreshCw className="h-6 w-6 animate-spin text-teal-400" />
                <span className="text-xs font-medium text-slate-500">
                  Loading call feed data...
                </span>
              </div>
            ) : stats?.recent_calls.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2 py-12 text-slate-600">
                <Calendar className="h-10 w-10 opacity-30" />
                <span className="text-xs font-semibold">
                  No calls logged yet. Play a call to test.
                </span>
              </div>
            ) : (
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="border-b border-slate-800/50 text-xs font-bold tracking-wider text-slate-400 uppercase">
                    <th className="px-4 py-3.5">Session Reference</th>
                    <th className="px-4 py-3.5">Start Time</th>
                    <th className="px-4 py-3.5">Duration</th>
                    <th className="px-4 py-3.5 text-center">Channel</th>
                    <th className="px-4 py-3.5 text-right">Outcome</th>
                  </tr>
                </thead>
                <tbody className="divide-slate-850/50 divide-y text-sm font-medium">
                  {stats?.recent_calls.map((call) => (
                    <tr
                      key={call.call_id}
                      className="animate-in fade-in transition-colors duration-200 hover:bg-slate-900/40"
                    >
                      <td className="px-4 py-3.5 font-mono text-xs text-slate-400">
                        {call.call_id || '--------'}
                      </td>
                      <td className="px-4 py-3.5 text-xs text-slate-300">
                        <div className="flex items-center gap-2">
                          <Calendar className="h-3.5 w-3.5 shrink-0 text-slate-500" />
                          {formatTimestamp(call.started_at)}
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-xs text-slate-300">
                        <div className="flex items-center gap-2">
                          <Clock className="h-3.5 w-3.5 shrink-0 text-slate-500" />
                          {formatDuration(call.started_at, call.ended_at)}
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-center">
                        <div className="inline-flex items-center justify-center gap-1.5 rounded border px-2 py-0.5 text-[11px] font-bold capitalize">
                          {call.channel === 'sip' ? (
                            <>
                              <Phone className="h-3 w-3 text-cyan-400" />
                              <span className="bg-gradient-to-r from-cyan-400 to-teal-400 bg-clip-text text-transparent">
                                SIP / Phone
                              </span>
                            </>
                          ) : (
                            <>
                              <Laptop className="h-3 w-3 text-violet-400" />
                              <span className="bg-gradient-to-r from-violet-400 to-indigo-400 bg-clip-text text-transparent">
                                Browser
                              </span>
                            </>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold ${
                            call.outcome === 'success'
                              ? 'border border-emerald-500/20 bg-emerald-500/10 text-emerald-400'
                              : 'border border-rose-500/20 bg-rose-500/10 text-rose-400'
                          }`}
                        >
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${call.outcome === 'success' ? 'bg-emerald-400' : 'bg-rose-400'}`}
                          ></span>
                          {call.outcome === 'success' ? 'Successful' : 'Failed'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
