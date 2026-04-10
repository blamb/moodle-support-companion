import type { SourcesResponse } from '../types';
import { SourceBadge } from './SourceBadge';

const SOURCE_LABELS: Record<string, string> = {
  moodle_docs: 'Moodle Docs',
  olproduction: 'OL Production',
  trubox: 'TRU Box',
  tru_faq: 'TRU FAQ',
};

interface FilterSidebarProps {
  sources: SourcesResponse | null;
  activeSource: string | null;
  onSourceChange: (source: string | null) => void;
}

export function FilterSidebar({
  sources,
  activeSource,
  onSourceChange,
}: FilterSidebarProps) {
  if (!sources || sources.sources.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <p className="text-sm text-slate-400">
          No sources indexed yet. Run ingestion first.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <h3 className="text-sm font-semibold text-slate-700 mb-3">Filter by source</h3>

      <div className="space-y-2">
        {/* All sources option */}
        <button
          onClick={() => onSourceChange(null)}
          className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
            activeSource === null
              ? 'bg-orange-50 text-orange-700 font-medium'
              : 'text-slate-600 hover:bg-slate-50'
          }`}
        >
          All sources
          <span className="float-right text-xs text-slate-400">
            {sources.total_chunks} chunks
          </span>
        </button>

        {sources.sources.map((s) => (
          <button
            key={s.source}
            onClick={() =>
              onSourceChange(activeSource === s.source ? null : s.source)
            }
            className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
              activeSource === s.source
                ? 'bg-orange-50 text-orange-700 font-medium'
                : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            {SOURCE_LABELS[s.source] || s.source}
            <span className="float-right text-xs text-slate-400">
              {s.document_count} docs
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
