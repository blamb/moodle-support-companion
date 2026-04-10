import { useSearch } from '../hooks/useSearch';
import { SearchBar } from './SearchBar';
import { ResultsList } from './ResultsList';
import { FilterSidebar } from './FilterSidebar';

interface SearchPageProps {
  onStartDiagnosis?: (text: string) => void;
}

export function SearchPage({ onStartDiagnosis }: SearchPageProps) {
  const {
    query,
    setQuery,
    results,
    loading,
    error,
    sourceFilter,
    setSourceFilter,
    sources,
  } = useSearch();

  return (
    <>
      {/* Search bar */}
      <div className="mb-6">
        <SearchBar query={query} onQueryChange={setQuery} loading={loading} />
      </div>

      {/* Error display */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Content area with sidebar */}
      <div className="flex gap-6">
        {/* Sidebar */}
        <aside className="w-56 flex-shrink-0 hidden md:block">
          <FilterSidebar
            sources={sources}
            activeSource={sourceFilter}
            onSourceChange={setSourceFilter}
          />
        </aside>

        {/* Results */}
        <div className="flex-1 min-w-0">
          <ResultsList
            results={results}
            loading={loading}
            query={query}
            onStartDiagnosis={onStartDiagnosis}
          />
        </div>
      </div>
    </>
  );
}
