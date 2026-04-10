import { useState, useCallback, useRef, useEffect } from 'react';
import type { SearchResponse, SourcesResponse } from '../types';

const API_BASE = '/api';

export function useSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);
  const [sources, setSources] = useState<SourcesResponse | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Fetch sources on mount
  useEffect(() => {
    fetch(`${API_BASE}/sources`)
      .then((res) => res.json())
      .then(setSources)
      .catch(() => {});
  }, []);

  const doSearch = useCallback(
    async (q: string, source: string | null) => {
      if (!q.trim() || q.trim().length < 2) {
        setResults(null);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({ q: q.trim(), limit: '15' });
        if (source) params.set('source', source);

        const res = await fetch(`${API_BASE}/search?${params}`);
        if (!res.ok) throw new Error(`Search failed: ${res.statusText}`);

        const data: SearchResponse = await res.json();
        setResults(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Search failed');
        setResults(null);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const handleQueryChange = useCallback(
    (newQuery: string) => {
      setQuery(newQuery);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        doSearch(newQuery, sourceFilter);
      }, 300);
    },
    [doSearch, sourceFilter]
  );

  const handleSourceFilter = useCallback(
    (source: string | null) => {
      setSourceFilter(source);
      if (query.trim().length >= 2) {
        doSearch(query, source);
      }
    },
    [doSearch, query]
  );

  return {
    query,
    setQuery: handleQueryChange,
    results,
    loading,
    error,
    sourceFilter,
    setSourceFilter: handleSourceFilter,
    sources,
  };
}
