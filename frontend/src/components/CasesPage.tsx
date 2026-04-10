import { useState, useEffect, useCallback } from 'react';
import { AnalyticsDashboard } from './AnalyticsDashboard';

interface CaseRecord {
  id: string;
  created_at: number;
  updated_at: number;
  summary: string;
  problem_description: string;
  diagnosis: string;
  resolution: string;
  tags: string[];
  difficulty: number;
  moodle_module: string;
  status: string;
}

type CasesView = 'list' | 'analytics';

export function CasesPage() {
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedCase, setSelectedCase] = useState<CaseRecord | null>(null);
  const [view, setView] = useState<CasesView>('list');

  // Tag filtering
  const [allTags, setAllTags] = useState<string[]>([]);
  const [activeTag, setActiveTag] = useState<string | null>(null);

  const fetchCases = useCallback(async (query?: string) => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (query?.trim()) params.set('q', query.trim());
      params.set('limit', '100');

      const res = await fetch(`/api/cases?${params}`);
      if (!res.ok) throw new Error('Failed to load cases');
      const data = await res.json();
      setCases(data.cases || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load cases');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchTags = useCallback(async () => {
    try {
      const res = await fetch('/api/cases/tags');
      if (res.ok) {
        const data = await res.json();
        setAllTags(data.tags || []);
      }
    } catch {
      // Tags are non-critical
    }
  }, []);

  const fetchByTag = useCallback(async (tag: string) => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`/api/cases/by-tag/${encodeURIComponent(tag)}`);
      if (!res.ok) throw new Error('Failed to load cases');
      const data = await res.json();
      setCases(data.cases || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load cases');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCases();
    fetchTags();
  }, [fetchCases, fetchTags]);

  const handleSearch = () => {
    setActiveTag(null);
    fetchCases(searchQuery);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  const handleTagClick = (tag: string) => {
    if (activeTag === tag) {
      setActiveTag(null);
      fetchCases();
    } else {
      setActiveTag(tag);
      setSearchQuery('');
      fetchByTag(tag);
    }
  };

  const handleExportCSV = async () => {
    try {
      const res = await fetch('/api/cases/export/csv');
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'moodle-support-cases.csv';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      setError('Failed to export CSV');
    }
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleDateString('en-CA', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const difficultyLabel = (d: number) => {
    const labels = ['', 'Simple', 'Easy', 'Moderate', 'Complex', 'Critical'];
    return labels[d] || '';
  };

  const difficultyColor = (d: number) => {
    const colors = ['', 'text-green-600 bg-green-50', 'text-green-600 bg-green-50',
      'text-yellow-600 bg-yellow-50', 'text-orange-600 bg-orange-50', 'text-red-600 bg-red-50'];
    return colors[d] || 'text-slate-600 bg-slate-50';
  };

  // Case detail view
  if (selectedCase) {
    return (
      <div>
        <button
          onClick={() => setSelectedCase(null)}
          className="text-sm text-slate-500 hover:text-slate-700 mb-4 flex items-center gap-1"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to cases
        </button>

        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <div className="flex items-start justify-between gap-4 mb-4">
            <h2 className="text-lg font-semibold text-slate-900">{selectedCase.summary}</h2>
            <div className="flex gap-2 flex-shrink-0">
              {selectedCase.difficulty > 0 && (
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${difficultyColor(selectedCase.difficulty)}`}>
                  {difficultyLabel(selectedCase.difficulty)}
                </span>
              )}
              <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                selectedCase.status === 'resolved' ? 'text-emerald-700 bg-emerald-50' :
                selectedCase.status === 'escalated' ? 'text-red-700 bg-red-50' :
                'text-yellow-700 bg-yellow-50'
              }`}>
                {selectedCase.status}
              </span>
            </div>
          </div>

          <p className="text-xs text-slate-400 mb-4">
            Created {formatDate(selectedCase.created_at)}
            {selectedCase.moodle_module && ` · Module: ${selectedCase.moodle_module}`}
          </p>

          {selectedCase.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-4">
              {selectedCase.tags.map((tag, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setSelectedCase(null);
                    handleTagClick(tag);
                  }}
                  className="text-xs px-2 py-0.5 rounded-full border border-slate-200 hover:border-purple-400 transition-colors cursor-pointer"
                  style={{ backgroundColor: 'var(--lti-purple-light)', color: 'var(--lti-purple)' }}
                >
                  {tag}
                </button>
              ))}
            </div>
          )}

          {selectedCase.problem_description && (
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-slate-700 mb-1">Problem</h3>
              <p className="text-sm text-slate-600 whitespace-pre-wrap">{selectedCase.problem_description}</p>
            </div>
          )}

          {selectedCase.diagnosis && (
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-slate-700 mb-1">Diagnosis</h3>
              <p className="text-sm text-slate-600 whitespace-pre-wrap">{selectedCase.diagnosis}</p>
            </div>
          )}

          {selectedCase.resolution && (
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-slate-700 mb-1">Resolution</h3>
              <p className="text-sm text-slate-600 whitespace-pre-wrap">{selectedCase.resolution}</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* View switcher + actions */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1 rounded-lg p-1" style={{ backgroundColor: 'var(--lti-purple-light)' }}>
          <button
            onClick={() => setView('list')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all"
            style={{
              backgroundColor: view === 'list' ? 'var(--lti-purple)' : 'transparent',
              color: view === 'list' ? 'white' : 'var(--lti-navy)',
            }}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
            </svg>
            Cases
          </button>
          <button
            onClick={() => setView('analytics')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all"
            style={{
              backgroundColor: view === 'analytics' ? 'var(--lti-purple)' : 'transparent',
              color: view === 'analytics' ? 'white' : 'var(--lti-navy)',
            }}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Analytics
          </button>
        </div>

        <button
          onClick={handleExportCSV}
          className="lti-btn-outline flex items-center gap-1.5"
          title="Export all cases as CSV"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Export CSV
        </button>
      </div>

      {/* Analytics view */}
      {view === 'analytics' && <AnalyticsDashboard />}

      {/* List view */}
      {view === 'list' && (
        <>
          {/* Search bar */}
          <div className="flex gap-3 mb-4">
            <div className="flex-1 relative">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <svg className="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Search past cases..."
                className="w-full pl-12 pr-4 py-3 border border-slate-200 rounded-xl bg-white shadow-sm
                           focus:outline-none focus:ring-2 focus:ring-orange-400 focus:border-transparent
                           placeholder:text-slate-400"
              />
            </div>
            <button
              onClick={handleSearch}
              className="lti-btn-gold rounded-xl text-sm"
            >
              Search
            </button>
          </div>

          {/* Tag filter pills */}
          {allTags.length > 0 && (
            <div className="mb-4">
              <div className="flex flex-wrap gap-1.5">
                {allTags.map((tag) => (
                  <button
                    key={tag}
                    onClick={() => handleTagClick(tag)}
                    className="text-xs px-2.5 py-1 rounded-full border transition-all"
                    style={{
                      backgroundColor: activeTag === tag ? 'var(--lti-purple)' : 'var(--lti-purple-light)',
                      color: activeTag === tag ? 'white' : 'var(--lti-purple)',
                      borderColor: activeTag === tag ? 'var(--lti-purple)' : 'transparent',
                    }}
                  >
                    {tag}
                  </button>
                ))}
                {activeTag && (
                  <button
                    onClick={() => { setActiveTag(null); fetchCases(); }}
                    className="text-xs px-2 py-1 text-slate-400 hover:text-slate-600"
                  >
                    Clear filter
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div className="text-center py-12 text-slate-400">
              <div className="h-8 w-8 border-2 border-orange-400 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p>Loading cases...</p>
            </div>
          )}

          {/* Empty state */}
          {!loading && cases.length === 0 && (
            <div className="text-center py-16 text-slate-400">
              <svg className="mx-auto h-12 w-12 mb-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              <p className="text-lg">No cases yet</p>
              <p className="text-sm mt-1">
                {activeTag
                  ? `No cases tagged "${activeTag}".`
                  : searchQuery
                    ? 'No cases match your search. Try different terms.'
                    : 'Cases will appear here when you save diagnostic sessions.'}
              </p>
            </div>
          )}

          {/* Cases list */}
          {!loading && cases.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm text-slate-500 mb-3">
                {cases.length} case{cases.length !== 1 ? 's' : ''}
                {activeTag && ` tagged "${activeTag}"`}
                {searchQuery && !activeTag && ` matching "${searchQuery}"`}
              </p>
              {cases.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setSelectedCase(c)}
                  className="w-full text-left bg-white rounded-lg border border-slate-200 p-4
                             hover:shadow-md hover:border-slate-300 transition-all"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-semibold text-slate-900 mb-1 truncate">
                        {c.summary}
                      </h3>
                      <p className="text-xs text-slate-500 line-clamp-2">
                        {c.problem_description || c.diagnosis || 'No description'}
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <span className="text-xs text-slate-400">{formatDate(c.created_at)}</span>
                      <div className="flex gap-1">
                        {c.difficulty > 0 && (
                          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${difficultyColor(c.difficulty)}`}>
                            {difficultyLabel(c.difficulty)}
                          </span>
                        )}
                        {c.moodle_module && (
                          <span className="text-xs bg-orange-50 text-orange-600 px-1.5 py-0.5 rounded">
                            {c.moodle_module}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  {c.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {c.tags.map((tag, i) => (
                        <span key={i} className="text-xs px-1.5 py-0.5 rounded"
                              style={{ backgroundColor: 'var(--lti-purple-light)', color: 'var(--lti-purple)' }}>
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
