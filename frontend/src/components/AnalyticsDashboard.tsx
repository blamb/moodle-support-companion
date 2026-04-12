import { useState, useEffect } from 'react';

interface Analytics {
  total_cases: number;
  by_status: Record<string, number>;
  by_difficulty: Record<string, number>;
  by_module: Record<string, number>;
  top_tags: Array<{ tag: string; count: number }>;
  timeline: Array<{ week: string; count: number }>;
  avg_resolution_hours: number;
  recent_30d: number;
  previous_30d: number;
}

export function AnalyticsDashboard() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/cases/analytics');
      if (!res.ok) throw new Error('Failed to load analytics');
      const data = await res.json();
      setAnalytics(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="text-center py-8 text-slate-500" role="status">
        <div className="h-8 w-8 border-2 border-orange-400 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p>Loading analytics...</p>
      </div>
    );
  }

  if (error || !analytics) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700" role="alert">
        {error || 'No analytics data available'}
      </div>
    );
  }

  const trendPercent = analytics.previous_30d > 0
    ? Math.round(((analytics.recent_30d - analytics.previous_30d) / analytics.previous_30d) * 100)
    : analytics.recent_30d > 0 ? 100 : 0;

  const maxTimelineCount = Math.max(...analytics.timeline.map(t => t.count), 1);

  const difficultyLabels: Record<string, string> = {
    '1': 'Simple', '2': 'Easy', '3': 'Moderate', '4': 'Complex', '5': 'Critical'
  };
  const difficultyColors: Record<string, string> = {
    '1': 'bg-green-400', '2': 'bg-green-300', '3': 'bg-yellow-400', '4': 'bg-orange-400', '5': 'bg-red-400'
  };

  return (
    <div className="space-y-6">
      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Total Cases</p>
          <p className="text-2xl font-bold mt-1" style={{ color: 'var(--lti-navy)' }}>
            {analytics.total_cases}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Last 30 Days</p>
          <p className="text-2xl font-bold mt-1" style={{ color: 'var(--lti-navy)' }}>
            {analytics.recent_30d}
          </p>
          {trendPercent !== 0 && (
            <p className={`text-xs mt-1 ${trendPercent > 0 ? 'text-orange-500' : 'text-green-500'}`}>
              {trendPercent > 0 ? '↑' : '↓'} {Math.abs(trendPercent)}% vs prior 30d
            </p>
          )}
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Avg Resolution</p>
          <p className="text-2xl font-bold mt-1" style={{ color: 'var(--lti-navy)' }}>
            {analytics.avg_resolution_hours < 24
              ? `${analytics.avg_resolution_hours}h`
              : `${Math.round(analytics.avg_resolution_hours / 24)}d`
            }
          </p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Status</p>
          <div className="flex gap-3 mt-2">
            {Object.entries(analytics.by_status).map(([status, count]) => (
              <div key={status} className="text-center">
                <p className="text-lg font-bold" style={{ color: 'var(--lti-navy)' }}>{count}</p>
                <p className="text-xs text-slate-500 capitalize">{status}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Timeline chart */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Cases per Week (12 weeks)</h3>
        <div className="flex items-end gap-1 h-32" role="img" aria-label={`Cases per week chart. ${analytics.timeline.filter(w => w.count > 0).length} active weeks out of 12.`}>
          {analytics.timeline.map((week, i) => (
            <div key={i} className="flex-1 flex flex-col items-center gap-1">
              <div
                className="w-full rounded-t transition-all"
                style={{
                  height: `${Math.max((week.count / maxTimelineCount) * 100, 4)}%`,
                  backgroundColor: week.count > 0 ? 'var(--lti-purple)' : '#e2e8f0',
                  minHeight: '4px',
                }}
                title={`${week.week}: ${week.count} cases`}
              />
              <span className="text-[10px] text-slate-500 leading-tight whitespace-nowrap">
                {week.week}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Two-column detail */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* Difficulty distribution */}
        {Object.keys(analytics.by_difficulty).length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-4" role="img" aria-label={`Difficulty distribution chart. ${Object.entries(analytics.by_difficulty).map(([level, count]) => `${difficultyLabels[level] || 'Level ' + level}: ${count}`).join(', ')}.`}>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">Difficulty Distribution</h3>
            <div className="space-y-2">
              {Object.entries(analytics.by_difficulty).map(([level, count]) => {
                const pct = analytics.total_cases > 0 ? (count / analytics.total_cases) * 100 : 0;
                return (
                  <div key={level} className="flex items-center gap-2">
                    <span className="text-xs text-slate-500 w-16">{difficultyLabels[level] || `Level ${level}`}</span>
                    <div className="flex-1 h-5 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${difficultyColors[level] || 'bg-slate-300'}`}
                        style={{ width: `${Math.max(pct, 2)}%` }}
                      />
                    </div>
                    <span className="text-xs font-medium text-slate-600 w-8 text-right">{count}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Top modules */}
        {Object.keys(analytics.by_module).length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-4" role="img" aria-label={`Top Moodle modules chart. ${Object.entries(analytics.by_module).slice(0, 8).map(([mod, count]) => `${mod}: ${count}`).join(', ')}.`}>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">Top Moodle Modules</h3>
            <div className="space-y-2">
              {Object.entries(analytics.by_module).slice(0, 8).map(([mod, count]) => {
                const pct = analytics.total_cases > 0 ? (count / analytics.total_cases) * 100 : 0;
                return (
                  <div key={mod} className="flex items-center gap-2">
                    <span className="text-xs text-slate-500 w-20 truncate capitalize">{mod}</span>
                    <div className="flex-1 h-5 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${Math.max(pct, 2)}%`, backgroundColor: 'var(--lti-gold)' }}
                      />
                    </div>
                    <span className="text-xs font-medium text-slate-600 w-8 text-right">{count}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Top tags */}
      {analytics.top_tags.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Most Used Tags</h3>
          <div className="flex flex-wrap gap-2">
            {analytics.top_tags.map(({ tag, count }) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full border"
                style={{
                  backgroundColor: 'var(--lti-purple-light)',
                  borderColor: 'var(--lti-purple)',
                  color: 'var(--lti-purple)',
                }}
              >
                {tag}
                <span className="font-bold">{count}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {analytics.total_cases === 0 && (
        <div className="text-center py-8 text-slate-500">
          <p className="text-lg">No cases tracked yet</p>
          <p className="text-sm mt-1">Analytics will populate as your team saves diagnostic sessions as cases.</p>
        </div>
      )}
    </div>
  );
}
