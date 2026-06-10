import { useState, useCallback } from 'react';
import type { ParseResponse, ImportMode } from '../types';

const API_BASE = '/api';

export function useQuestionImport() {
  const [text, setText] = useState('');
  const [mode, setMode] = useState<ImportMode>('auto');
  const [result, setResult] = useState<ParseResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const extractFromFile = useCallback(async (file: File) => {
    setUploading(true);
    setError(null);
    setNote(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API_BASE}/questions/extract`, {
        method: 'POST',
        body: form,
      });
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
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Conversion failed.');
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [text, mode]);

  const reset = useCallback(() => {
    setText('');
    setResult(null);
    setError(null);
    setNote(null);
  }, []);

  return {
    text,
    setText,
    mode,
    setMode,
    result,
    loading,
    error,
    note,
    uploading,
    convert,
    reset,
    extractFromFile,
  };
}
