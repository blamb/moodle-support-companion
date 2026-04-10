import type { SearchResponse } from '../types';
import { ResultCard } from './ResultCard';

interface ResultsListProps {
  results: SearchResponse | null;
  loading: boolean;
  query: string;
  onStartDiagnosis?: (text: string) => void;
}

export function ResultsList({ results, loading, query, onStartDiagnosis }: ResultsListProps) {
  if (!query.trim()) {
    return (
      <div className="text-center py-16 text-slate-400">
        <svg
          className="mx-auto h-12 w-12 mb-4 text-slate-300"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <p className="text-lg">Search the knowledge base</p>
        <p className="text-sm mt-1">
          Describe a problem, paste an error, or search for documentation
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="text-center py-12 text-slate-400">
        <div className="h-8 w-8 border-2 border-orange-400 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p>Searching...</p>
      </div>
    );
  }

  if (results && results.results.length === 0) {
    return (
      <div className="text-center py-12 text-slate-400">
        <p className="text-lg">No results found</p>
        <p className="text-sm mt-1">Try different terms or broaden your search</p>
      </div>
    );
  }

  if (!results) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">
          {results.total} result{results.total !== 1 ? 's' : ''} for "{results.query}"
        </p>
        {onStartDiagnosis && (
          <button
            onClick={() => onStartDiagnosis(query)}
            className="text-xs font-medium flex items-center gap-1"
            style={{ color: 'var(--lti-purple)' }}
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            Diagnose this issue
          </button>
        )}
      </div>
      {results.results.map((result, index) => (
        <ResultCard key={`${result.source}-${result.title}-${result.chunk_index}`} result={result} rank={index + 1} />
      ))}
    </div>
  );
}
