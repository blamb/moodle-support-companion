import { useState } from 'react';

interface SaveCaseDialogProps {
  sessionId: string;
  onClose: () => void;
  onSaved: (caseId: string) => void;
}

export function SaveCaseDialog({ sessionId, onClose, onSaved }: SaveCaseDialogProps) {
  const [summary, setSummary] = useState('');
  const [tags, setTags] = useState('');
  const [difficulty, setDifficulty] = useState(3);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSave = async () => {
    if (!summary.trim()) {
      setError('Summary is required');
      return;
    }

    setSaving(true);
    setError('');

    try {
      const res = await fetch('/api/cases', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          summary: summary.trim(),
          tags: tags.split(',').map(t => t.trim()).filter(Boolean),
          difficulty,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to save case');
      }

      const data = await res.json();
      onSaved(data.case_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Save as Case</h3>

        {/* Summary */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Summary *
          </label>
          <input
            type="text"
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            placeholder="Brief description of the issue and resolution"
            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2"
            style={{ '--tw-ring-color': 'var(--lti-purple)' } as any}
          />
        </div>

        {/* Tags */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Tags (comma-separated)
          </label>
          <input
            type="text"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="gradebook, quiz, permissions"
            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2"
              style={{ '--tw-ring-color': 'var(--lti-purple)' } as any}
          />
        </div>

        {/* Difficulty */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Difficulty (1-5)
          </label>
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                onClick={() => setDifficulty(n)}
                className="w-10 h-10 rounded-lg text-sm font-medium border transition-colors"
                style={{
                  backgroundColor: difficulty === n ? 'var(--lti-purple)' : 'white',
                  color: difficulty === n ? 'white' : '#64748b',
                  borderColor: difficulty === n ? 'var(--lti-purple)' : '#e2e8f0',
                }}
              >
                {n}
              </button>
            ))}
          </div>
        </div>

        {/* Error */}
        {error && (
          <p className="text-sm text-red-600 mb-3">{error}</p>
        )}

        {/* Actions */}
        <div className="flex gap-3 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="lti-btn-gold text-sm"
          >
            {saving ? 'Saving...' : 'Save Case'}
          </button>
        </div>
      </div>
    </div>
  );
}
