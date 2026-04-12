interface SearchBarProps {
  query: string;
  onQueryChange: (query: string) => void;
  loading: boolean;
}

export function SearchBar({ query, onQueryChange, loading }: SearchBarProps) {
  return (
    <div className="relative">
      <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
        <svg
          className="h-5 w-5"
          style={{ color: 'var(--lti-purple)' }}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
      </div>
      <input
        type="text"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        aria-label="Search the knowledge base"
        placeholder="Describe the issue or search documentation..."
        className="w-full pl-12 pr-12 py-4 text-lg border border-slate-200 rounded-xl
                   bg-white shadow-sm focus:outline-none focus:ring-2
                   focus:border-transparent placeholder:text-slate-400 transition-shadow"
        style={{ '--tw-ring-color': 'var(--lti-purple)' } as any}
      />
      {loading && (
        <div className="absolute inset-y-0 right-0 pr-4 flex items-center">
          <div
            className="h-5 w-5 border-2 border-t-transparent rounded-full animate-spin"
            style={{ borderColor: 'var(--lti-gold)', borderTopColor: 'transparent' }}
          />
        </div>
      )}
    </div>
  );
}
