import Markdown from 'react-markdown';
import { ModeBadge } from './ModeBadge';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  mode?: string;
  sources?: Array<{ title: string; source: string; canonical_url?: string }>;
  urlContexts?: Array<{ context_summary: string; url: string }>;
  isStreaming?: boolean;
}

export function ChatMessage({
  role,
  content,
  mode,
  sources,
  urlContexts,
  isStreaming,
}: ChatMessageProps) {
  if (role === 'user') {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[80%]">
          {urlContexts && urlContexts.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-1 justify-end">
              {urlContexts.map((ctx, i) => (
                <span
                  key={i}
                  className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full"
                >
                  {ctx.context_summary}
                </span>
              ))}
            </div>
          )}
          <div className="text-white rounded-2xl rounded-br-sm px-4 py-3 text-sm whitespace-pre-wrap"
               style={{ backgroundColor: 'var(--lti-purple)' }}>
            {content}
          </div>
        </div>
      </div>
    );
  }

  // Assistant message
  return (
    <div className="flex justify-start mb-4">
      <div className="max-w-[85%]">
        {/* Mode badge */}
        {mode && (
          <div className="mb-1">
            <ModeBadge mode={mode} />
          </div>
        )}

        {/* Message content — rendered as markdown */}
        <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-sm px-4 py-3 text-sm leading-relaxed shadow-sm prose prose-sm prose-slate max-w-none
                        prose-headings:text-slate-800 prose-headings:font-semibold prose-headings:mt-3 prose-headings:mb-1
                        prose-p:my-1.5 prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5
                        prose-strong:text-slate-800 prose-a:text-orange-600 prose-a:no-underline hover:prose-a:underline
                        prose-code:bg-slate-100 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-slate-700 prose-code:before:content-none prose-code:after:content-none">
          <Markdown>{content}</Markdown>
          {isStreaming && (
            <span className="inline-block w-2 h-4 bg-orange-400 ml-0.5 animate-pulse rounded-sm" aria-hidden="true" />
          )}
        </div>

        {/* Source references */}
        {sources && sources.length > 0 && (
          <details className="mt-1">
            <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-600">
              {sources.length} source{sources.length > 1 ? 's' : ''} consulted
            </summary>
            <div className="mt-1 space-y-1">
              {sources.map((src, i) => (
                <div key={i} className="text-xs text-slate-500 flex items-center gap-1">
                  <span className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">
                    {src.source === 'moodle_docs' ? 'Docs' :
                     src.source === 'olproduction' ? 'OL Prod' :
                     src.source === 'trubox' ? 'TRU Box' : src.source}
                  </span>
                  {src.canonical_url ? (
                    <a
                      href={src.canonical_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-orange-600 underline"
                    >
                      {src.title}
                    </a>
                  ) : (
                    <span>{src.title}</span>
                  )}
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}
