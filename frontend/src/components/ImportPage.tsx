import { useState, useRef } from 'react';
import { useQuestionImport } from '../hooks/useQuestionImport';
import type { ParsedQuestion, ExportFormat, ImportMode } from '../types';

const MODE_OPTIONS: Array<{ key: ImportMode; label: string; hint: string }> = [
  { key: 'auto', label: 'Smart', hint: 'Rules first, AI cleans up only what rules can’t read' },
  { key: 'rules', label: 'Rules only', hint: 'Deterministic, instant, fully private — no AI' },
  { key: 'ai', label: 'AI cleanup', hint: 'Send everything to Claude — best for very messy input' },
];

const FORMAT_OPTIONS: Array<{ key: ExportFormat; label: string; ext: string; note: string }> = [
  { key: 'gift', label: 'GIFT', ext: 'txt', note: 'Handles every question type' },
  { key: 'xml', label: 'Moodle XML', ext: 'xml', note: 'Safest for rich text & feedback' },
  { key: 'aiken', label: 'Aiken', ext: 'txt', note: 'Multiple choice / true-false only' },
];

const BADGE_STYLES: Record<string, string> = {
  multichoice: 'bg-blue-50 text-blue-700 border-blue-200',
  truefalse: 'bg-green-50 text-green-700 border-green-200',
  shortanswer: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  essay: 'bg-pink-50 text-pink-700 border-pink-200',
  matching: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  numerical: 'bg-amber-50 text-amber-700 border-amber-200',
};

const SAMPLE = `1. What is the capital of France?
A) London
B) Paris
C) Berlin
Correct answer: B

2. Which are primary colours? (select all)
*A) Red
B) Green
*C) Blue

SHORT: Who wrote Romeo and Juliet?
= Shakespeare
= William Shakespeare

ESSAY: Explain why photosynthesis matters to life on Earth.`;

function QuestionCard({ q }: { q: ParsedQuestion }) {
  const badge = BADGE_STYLES[q.qtype] ?? 'bg-slate-100 text-slate-600 border-slate-200';
  const needsReview = q.warnings.length > 0;

  return (
    <div
      className={`rounded-lg border p-4 bg-white ${
        needsReview ? 'border-amber-300 ring-1 ring-amber-100' : 'border-slate-200'
      }`}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <p className="font-medium text-slate-900 text-sm">
          <span className="text-slate-400 font-mono mr-1">{q.number}.</span>
          {q.text}
        </p>
        <span
          className={`shrink-0 inline-block px-2 py-0.5 rounded text-[11px] font-semibold uppercase border ${badge}`}
        >
          {q.type_label}
          {q.qtype === 'multichoice' && !q.single ? ' · multi' : ''}
        </span>
      </div>

      {/* Options */}
      {q.options.length > 0 && (
        <ul className="space-y-1 ml-1">
          {q.options.map((o, i) => {
            const correct = o.fraction > 0;
            return (
              <li
                key={i}
                className={`text-sm flex items-baseline gap-1.5 ${
                  correct ? 'text-green-700 font-medium' : 'text-slate-500'
                }`}
              >
                <span aria-hidden className="w-3 inline-block">{correct ? '✓' : '·'}</span>
                <span>{o.text}</span>
                {o.fraction !== 0 && o.fraction !== 100 && (
                  <span className="text-xs text-slate-400">[{o.fraction}%]</span>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {/* True/False answer */}
      {q.qtype === 'truefalse' && (
        <p className="text-sm text-green-700 font-medium ml-1">
          ✓ Answer: {q.correct === 'true' ? 'True' : 'False'}
        </p>
      )}

      {/* Short answer / numerical accepted answers */}
      {q.answers.length > 0 && (
        <ul className="space-y-1 ml-1">
          {q.answers.map((a, i) => (
            <li key={i} className="text-sm text-green-700">
              {'✓'} {a.text}
              {a.tolerance ? <span className="text-xs text-slate-400"> (±{a.tolerance})</span> : null}
            </li>
          ))}
        </ul>
      )}

      {/* Matching pairs */}
      {q.pairs.length > 0 && (
        <ul className="space-y-1 ml-1">
          {q.pairs.map((p, i) => (
            <li key={i} className="text-sm text-slate-600">
              {p.question} <span className="text-slate-400">{'→'}</span> {p.answer}
            </li>
          ))}
        </ul>
      )}

      {q.qtype === 'essay' && (
        <p className="text-sm text-slate-400 italic ml-1">(Open-ended response)</p>
      )}

      {/* Per-question review warnings */}
      {needsReview && (
        <div className="mt-2 pt-2 border-t border-amber-100">
          {q.warnings.map((w, i) => (
            <p key={i} className="text-xs text-amber-700 flex items-start gap-1.5">
              <span aria-hidden>{'⚠'}</span>
              <span>{w}</span>
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

export function ImportPage() {
  const { text, setText, mode, setMode, result, loading, error, note, uploading, convert, extractFromFile } =
    useQuestionImport();
  const [format, setFormat] = useState<ExportFormat>('gift');
  const [showHelp, setShowHelp] = useState(false);
  const [copied, setCopied] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const onFileChosen = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) extractFromFile(file);
    e.target.value = ''; // allow re-uploading the same file
  };

  const exportContent = result ? result.exports[format] : '';
  const fmtMeta = FORMAT_OPTIONS.find((f) => f.key === format)!;

  const download = () => {
    if (!exportContent) return;
    const blob = new Blob([exportContent], {
      type: format === 'xml' ? 'application/xml' : 'text/plain',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `moodle_questions.${fmtMeta.ext}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const copy = async () => {
    if (!exportContent) return;
    try {
      await navigator.clipboard.writeText(exportContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard may be blocked; ignore */
    }
  };

  return (
    <div className="space-y-5">
      {/* Intro */}
      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <h2 className="text-lg font-bold mb-1" style={{ color: 'var(--lti-navy)' }}>
          Question Import Helper
        </h2>
        <p className="text-sm text-slate-600">
          Paste questions an instructor sent — even messy or inconsistently formatted — and get a
          clean Moodle import file (GIFT, XML, or Aiken). Anything the parser is unsure about is{' '}
          <span className="font-medium text-amber-700">flagged for review</span> rather than dropped.
        </p>
        <button
          onClick={() => setShowHelp((s) => !s)}
          className="mt-3 text-xs font-medium"
          style={{ color: 'var(--lti-purple-mid)' }}
        >
          {showHelp ? 'Hide' : 'Show'} accepted formats &amp; tips
        </button>
        {showHelp && (
          <div className="mt-3 text-xs text-slate-600 space-y-2 border-t border-slate-100 pt-3">
            <p>
              <strong>Multiple choice:</strong> number the question, list options as{' '}
              <code className="bg-slate-100 px-1 rounded">A)</code> or{' '}
              <code className="bg-slate-100 px-1 rounded">A.</code>, then mark the answer with{' '}
              <code className="bg-slate-100 px-1 rounded">Correct answer: B</code>, an asterisk
              (<code className="bg-slate-100 px-1 rounded">*B) Paris</code>), or <strong>bold</strong>.
              Mark several options correct for a multiple-response question.
            </p>
            <p>
              <strong>Partial credit:</strong> add percentages —{' '}
              <code className="bg-slate-100 px-1 rounded">A) Red 33.33%</code>,{' '}
              <code className="bg-slate-100 px-1 rounded">B) Green -50%</code>.
            </p>
            <p>
              <strong>Other types:</strong> start a line with{' '}
              <code className="bg-slate-100 px-1 rounded">SHORT:</code>,{' '}
              <code className="bg-slate-100 px-1 rounded">ESSAY:</code>,{' '}
              <code className="bg-slate-100 px-1 rounded">MATCH:</code>, or{' '}
              <code className="bg-slate-100 px-1 rounded">NUM:</code>. Short-answer / numerical
              answers go on lines starting with <code className="bg-slate-100 px-1 rounded">=</code>;
              matching pairs use <code className="bg-slate-100 px-1 rounded">Item -&gt; Match</code>.
            </p>
            <p className="text-slate-500">
              Don&apos;t worry about getting it perfect — <strong>Smart</strong> mode uses Claude to
              clean up whatever the rules can&apos;t read.
            </p>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <div className="flex items-center justify-between mb-2">
          <label htmlFor="qimport-input" className="text-sm font-medium text-slate-700">
            Paste questions
          </label>
          <div className="flex items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".docx,.txt,.md"
              onChange={onFileChosen}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="text-xs font-medium flex items-center gap-1 disabled:opacity-50"
              style={{ color: 'var(--lti-purple-mid)' }}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
              {uploading ? 'Reading…' : 'Upload .docx / .txt'}
            </button>
            <button
              onClick={() => setText(SAMPLE)}
              className="text-xs text-slate-400 hover:text-slate-600"
            >
              Load sample
            </button>
          </div>
        </div>
        {note && (
          <div className="mb-2 p-2.5 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700">
            {note}
          </div>
        )}
        <textarea
          id="qimport-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={12}
          placeholder="Paste the instructor's questions here…"
          className="w-full p-3 border border-slate-300 rounded-lg font-mono text-[13px] resize-y
                     focus:outline-none focus:border-[#2d1b69] focus:ring-2 focus:ring-[#2d1b69]/10"
        />

        {/* Mode selector */}
        <div className="mt-4">
          <p className="text-xs font-medium text-slate-500 mb-1.5">How should we read it?</p>
          <div className="flex flex-wrap gap-2">
            {MODE_OPTIONS.map((m) => (
              <button
                key={m.key}
                onClick={() => setMode(m.key)}
                title={m.hint}
                className={`px-3 py-1.5 rounded-md text-sm font-medium border transition-colors ${
                  mode === m.key
                    ? 'text-white border-transparent'
                    : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
                }`}
                style={mode === m.key ? { backgroundColor: 'var(--lti-purple)' } : undefined}
              >
                {m.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-slate-400 mt-1.5">
            {MODE_OPTIONS.find((m) => m.key === mode)?.hint}
          </p>
        </div>

        {error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700" role="alert">
            {error}
          </div>
        )}

        <button
          onClick={convert}
          disabled={loading || !text.trim()}
          className="lti-btn-gold mt-4 w-full"
        >
          {loading ? 'Converting…' : 'Convert questions'}
        </button>
      </div>

      {/* Results */}
      {result && (
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          {/* Summary bar */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mb-4">
            <h3 className="text-base font-bold" style={{ color: 'var(--lti-navy)' }}>
              {result.summary.total} question{result.summary.total === 1 ? '' : 's'} detected
            </h3>
            {result.summary.needs_review > 0 && (
              <span className="text-sm text-amber-700 font-medium">
                {'⚠'} {result.summary.needs_review} need review
              </span>
            )}
            {result.used_ai && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200">
                AI-assisted
              </span>
            )}
            {Object.entries(result.summary.by_type).map(([type, n]) => (
              <span key={type} className="text-xs text-slate-400">
                {n} {type}
              </span>
            ))}
          </div>

          {/* Global notes (e.g. AI summary) */}
          {result.warnings.length > 0 && (
            <div className="mb-4 p-3 bg-purple-50 border border-purple-200 rounded-lg">
              {result.warnings.map((w, i) => (
                <p key={i} className="text-sm text-purple-800">{w}</p>
              ))}
            </div>
          )}

          {/* Unparsed leftovers */}
          {result.unparsed.length > 0 && (
            <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <p className="text-sm font-medium text-amber-800 mb-1.5">
                {result.unparsed.length} block{result.unparsed.length === 1 ? '' : 's'} couldn&apos;t be
                turned into a question:
              </p>
              <ul className="space-y-1.5">
                {result.unparsed.map((u, i) => (
                  <li key={i} className="text-xs text-amber-700">
                    <span className="italic">{u.reason}</span>
                    <pre className="mt-0.5 whitespace-pre-wrap font-mono text-amber-900/70 bg-amber-100/50 p-1.5 rounded">
                      {u.text.length > 240 ? u.text.slice(0, 240) + '…' : u.text}
                    </pre>
                  </li>
                ))}
              </ul>
              {mode === 'rules' && (
                <p className="text-xs text-amber-700 mt-2">
                  Tip: switch to <strong>Smart</strong> or <strong>AI cleanup</strong> mode to let
                  Claude interpret these.
                </p>
              )}
            </div>
          )}

          {/* Question preview */}
          <div className="space-y-2.5 max-h-[480px] overflow-y-auto pr-1">
            {result.questions.map((q) => (
              <QuestionCard key={q.number} q={q} />
            ))}
          </div>

          {/* Export controls */}
          {result.questions.length > 0 && (
            <div className="mt-5 pt-4 border-t border-slate-100">
              <p className="text-xs font-medium text-slate-500 mb-1.5">Download as</p>
              <div className="flex flex-wrap gap-2 mb-2">
                {FORMAT_OPTIONS.map((f) => (
                  <button
                    key={f.key}
                    onClick={() => setFormat(f.key)}
                    title={f.note}
                    className={`px-3 py-1.5 rounded-md text-sm font-medium border transition-colors ${
                      format === f.key
                        ? 'text-white border-transparent'
                        : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
                    }`}
                    style={format === f.key ? { backgroundColor: 'var(--lti-purple-mid)' } : undefined}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
              <p className="text-xs text-slate-400 mb-3">{fmtMeta.note}.</p>

              {format === 'aiken' && result.exports.aiken_skipped.length > 0 && (
                <div className="mb-3 p-2.5 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
                  Aiken can&apos;t hold {result.exports.aiken_skipped.length} of these questions
                  (short answer, essay, matching, etc.). Use GIFT or XML to include everything.
                </div>
              )}

              <div className="flex gap-2">
                <button onClick={download} className="lti-btn-gold">
                  Download .{fmtMeta.ext}
                </button>
                <button onClick={copy} className="lti-btn-outline">
                  {copied ? 'Copied!' : 'Copy to clipboard'}
                </button>
              </div>

              <p className="text-xs text-slate-400 mt-3">
                In Moodle: <span className="text-slate-500">Question bank → Import</span>, choose the{' '}
                <strong>{fmtMeta.label}</strong> format, and upload this file.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
