import type { SearchResult } from '../types';
import { SourceBadge } from './SourceBadge';

interface ResultCardProps {
  result: SearchResult;
  rank: number;
}

export function ResultCard({ result, rank }: ResultCardProps) {
  const scorePercent = Math.round(result.score * 100);

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-5 hover:shadow-md transition-shadow">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm text-slate-400 font-mono">#{rank}</span>
          <SourceBadge source={result.source} />
          {result.categories.map((cat) => (
            <span
              key={cat}
              className="inline-flex items-center px-2 py-0.5 rounded text-xs
                         bg-slate-100 text-slate-600 border border-slate-200"
            >
              {cat}
            </span>
          ))}
        </div>
        <span
          className={`text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${
            scorePercent >= 60
              ? 'bg-green-50 text-green-700'
              : scorePercent >= 40
              ? 'bg-yellow-50 text-yellow-700'
              : 'bg-slate-50 text-slate-500'
          }`}
        >
          {scorePercent}% match
        </span>
      </div>

      {/* Title */}
      <h3 className="text-base font-semibold text-slate-900 mb-2">
        {result.canonical_url ? (
          <a
            href={result.canonical_url}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-[#2d1b69] transition-colors"
          >
            {result.title}
            <svg
              className="inline-block ml-1 h-3.5 w-3.5 text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
              />
            </svg>
          </a>
        ) : (
          result.title
        )}
      </h3>

      {/* Content snippet */}
      <p className="text-sm text-slate-600 leading-relaxed line-clamp-4 whitespace-pre-line">
        {result.text.length > 500 ? result.text.slice(0, 500) + '...' : result.text}
      </p>

      {/* Chunk info */}
      {result.total_chunks > 1 && (
        <p className="text-xs text-slate-400 mt-2">
          Section {result.chunk_index + 1} of {result.total_chunks}
        </p>
      )}
    </div>
  );
}
