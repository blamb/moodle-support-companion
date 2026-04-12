import { useState, useEffect, useRef } from 'react';

interface DraftReplyDialogProps {
  sessionId: string;
  onClose: () => void;
}

export function DraftReplyDialog({ sessionId, onClose }: DraftReplyDialogProps) {
  const [audience, setAudience] = useState('instructor');
  const [tone, setTone] = useState('professional');
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    previousFocusRef.current = document.activeElement as HTMLElement;
    dialogRef.current?.focus();
    return () => {
      previousFocusRef.current?.focus();
    };
  }, []);

  const handleGenerate = async () => {
    setLoading(true);
    setError('');
    setDraft('');

    try {
      const res = await fetch(`/api/conversation/${sessionId}/draft-reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audience, tone }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to generate draft');
      }

      const data = await res.json();
      setDraft(data.draft);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Generation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(draft);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const el = document.createElement('textarea');
      el.value = draft;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const optionStyle = (isActive: boolean) => ({
    backgroundColor: isActive ? 'var(--lti-purple-light)' : 'white',
    color: isActive ? 'var(--lti-purple)' : '#64748b',
    borderColor: isActive ? 'var(--lti-purple)' : '#e2e8f0',
    fontWeight: isActive ? 600 : 400,
  });

  return (
    <div
      className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="draft-reply-title"
      onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        tabIndex={-1}
        className="bg-white rounded-xl shadow-xl max-w-2xl w-full p-6 max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="draft-reply-title" className="text-lg font-semibold mb-4" style={{ color: 'var(--lti-navy)' }}>
          Draft Reply for TeamDynamix
        </h2>

        {!draft ? (
          <>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2" id="audience-label">Audience</label>
                <div className="space-y-1" role="radiogroup" aria-labelledby="audience-label">
                  {[
                    { value: 'instructor', label: 'Instructor / Faculty' },
                    { value: 'student', label: 'Student' },
                    { value: 'admin', label: 'IT Administrator' },
                  ].map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => setAudience(opt.value)}
                      role="radio"
                      aria-checked={audience === opt.value}
                      className="w-full text-left px-3 py-2 rounded-lg text-sm transition-colors border"
                      style={optionStyle(audience === opt.value)}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2" id="tone-label">Tone</label>
                <div className="space-y-1" role="radiogroup" aria-labelledby="tone-label">
                  {[
                    { value: 'professional', label: 'Professional' },
                    { value: 'friendly', label: 'Friendly' },
                    { value: 'brief', label: 'Brief / Concise' },
                  ].map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => setTone(opt.value)}
                      role="radio"
                      aria-checked={tone === opt.value}
                      className="w-full text-left px-3 py-2 rounded-lg text-sm transition-colors border"
                      style={optionStyle(tone === opt.value)}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

            <div className="flex gap-3 justify-end">
              <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800">
                Cancel
              </button>
              <button onClick={handleGenerate} disabled={loading} className="lti-btn-gold text-sm">
                {loading ? 'Generating...' : 'Generate Draft'}
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto mb-4">
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-sm whitespace-pre-wrap leading-relaxed">
                {draft}
              </div>
            </div>

            <div className="flex gap-3 justify-between">
              <button
                onClick={() => { setDraft(''); setError(''); }}
                className="lti-btn-outline"
              >
                Regenerate
              </button>
              <div className="flex gap-3">
                <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800">
                  Close
                </button>
                <button onClick={handleCopy} className="lti-btn-gold text-sm">
                  {copied ? 'Copied!' : 'Copy to Clipboard'}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
