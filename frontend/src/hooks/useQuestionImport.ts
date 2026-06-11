import { useState, useCallback, useRef } from 'react';
import type { ParseResponse, ImportMode, ParsedQuestion, QuestionExports } from '../types';

const API_BASE = '/api';

// Warnings that no longer apply once the user has set the correct answer.
const ANSWER_WARNING_PREFIXES = [
  'No correct answer',
  'True/False answer not marked',
  'Multiple correct answers detected',
];

function clearAnswerWarnings(q: ParsedQuestion): string[] {
  return q.warnings.filter((w) => !ANSWER_WARNING_PREFIXES.some((p) => w.startsWith(p)));
}

export function useQuestionImport() {
  const [text, setText] = useState('');
  const [mode, setMode] = useState<ImportMode>('auto');
  const [result, setResult] = useState<ParseResponse | null>(null);
  const [questions, setQuestions] = useState<ParsedQuestion[]>([]);
  const [exports, setExports] = useState<QuestionExports | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const serializeTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Re-generate the GIFT/XML/Aiken files from the current (edited) questions.
  const reserialize = useCallback((qs: ParsedQuestion[]) => {
    if (serializeTimer.current) clearTimeout(serializeTimer.current);
    serializeTimer.current = setTimeout(async () => {
      try {
        const res = await fetch(`${API_BASE}/questions/serialize`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ questions: qs }),
        });
        if (res.ok) {
          const data: { exports: QuestionExports } = await res.json();
          setExports(data.exports);
        }
      } catch {
        /* keep the previous exports if re-serialization fails */
      }
    }, 350);
  }, []);

  const extractFromFile = useCallback(async (file: File) => {
    setUploading(true);
    setError(null);
    setNote(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API_BASE}/questions/extract`, { method: 'POST', body: form });
      if (!res.ok) {
        let detail = `Couldn't read that file (${res.status})`;
        try {
          const body = await res.json();
          if (body?.detail) detail = body.detail;
        } catch {
          /* keep default */
        }
        throw new Error(detail);
      }
      const data: { text: string; note: string | null } = await res.json();
      setText(data.text);
      setResult(null);
      setQuestions([]);
      setExports(null);
      setNote(data.note ?? `Loaded ${file.name}. Review the text, then convert.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'File upload failed.');
    } finally {
      setUploading(false);
    }
  }, []);

  const convert = useCallback(async () => {
    if (!text.trim()) {
      setError('Paste some questions first.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/questions/parse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, mode }),
      });
      if (!res.ok) {
        let detail = `Request failed (${res.status})`;
        try {
          const body = await res.json();
          if (body?.detail) detail = body.detail;
        } catch {
          /* keep default */
        }
        throw new Error(detail);
      }
      const data: ParseResponse = await res.json();
      setResult(data);
      setQuestions(data.questions);
      setExports(data.exports);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Conversion failed.');
      setResult(null);
      setQuestions([]);
      setExports(null);
    } finally {
      setLoading(false);
    }
  }, [text, mode]);

  // User clicked an option in the preview to set / change the correct answer.
  const setCorrectOption = useCallback(
    (qIndex: number, optIndex: number) => {
      setQuestions((prev) => {
        const next = prev.map((q, i) => {
          if (i !== qIndex) return q;
          const options = q.options.map((o, j) => {
            if (q.single) {
              return { ...o, fraction: j === optIndex ? 100 : 0 };
            }
            // Multiple-answer: toggle this option's correctness.
            const on = j === optIndex ? o.fraction <= 0 : o.fraction > 0;
            return { ...o, fraction: on ? 1 : 0 }; // temp flag; normalized below
          });
          if (!q.single) {
            const correctCount = options.filter((o) => o.fraction > 0).length || 1;
            const share = Math.round((10000 / correctCount)) / 100; // even split
            options.forEach((o) => {
              o.fraction = o.fraction > 0 ? share : 0;
            });
          }
          return { ...q, options, warnings: clearAnswerWarnings(q) };
        });
        reserialize(next);
        return next;
      });
    },
    [reserialize]
  );

  // User clicked True / False on a true-false question.
  const setTrueFalse = useCallback(
    (qIndex: number, value: 'true' | 'false') => {
      setQuestions((prev) => {
        const next = prev.map((q, i) =>
          i === qIndex ? { ...q, correct: value, warnings: clearAnswerWarnings(q) } : q
        );
        reserialize(next);
        return next;
      });
    },
    [reserialize]
  );

  const reset = useCallback(() => {
    setText('');
    setResult(null);
    setQuestions([]);
    setExports(null);
    setError(null);
    setNote(null);
  }, []);

  return {
    text,
    setText,
    mode,
    setMode,
    result,
    questions,
    exports,
    loading,
    error,
    note,
    uploading,
    convert,
    reset,
    extractFromFile,
    setCorrectOption,
    setTrueFalse,
  };
}
