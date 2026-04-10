import { useState, useCallback, useRef, useEffect } from 'react';

const API_BASE = '/api';
const STORAGE_KEY = 'msc_recent_sessions';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  mode?: string;
  sources?: Array<{ title: string; source: string; canonical_url?: string; score?: number }>;
  urlContexts?: Array<{ context_summary: string; url: string }>;
}

interface MbzInfo {
  course_name: string;
  activity_count: number;
  activity_types: string[];
  summary: string;
}

export function useConversation() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingText, setStreamingText] = useState('');
  const [currentMode, setCurrentMode] = useState<string>('explore');
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mbzInfo, setMbzInfo] = useState<MbzInfo | null>(null);
  const [pendingScreenshot, setPendingScreenshot] = useState(false);
  const [htmlPageInfo, setHtmlPageInfo] = useState<string | null>(null);
  const [pendingSources, setPendingSources] = useState<Message['sources']>([]);
  const [pendingUrlContexts, setPendingUrlContexts] = useState<Message['urlContexts']>([]);
  const abortRef = useRef<AbortController | null>(null);

  const startSession = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/conversation`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to create session');
      const data = await res.json();
      setSessionId(data.session_id);
      setMessages([]);
      setError(null);
      setMbzInfo(null);
      return data.session_id;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start session');
      return null;
    }
  }, []);

  const sendMessage = useCallback(async (text: string) => {
    let sid = sessionId;
    if (!sid) {
      sid = await startSession();
      if (!sid) return;
    }

    // Add user message immediately
    const userMsg: Message = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setStreamingText('');
    setIsStreaming(true);
    setError(null);
    setPendingSources([]);
    setPendingUrlContexts([]);
    setPendingScreenshot(false);  // Screenshot will be consumed by this message

    // Track sources and URL contexts for this message
    let messageSources: Message['sources'] = [];
    let messageUrlContexts: Message['urlContexts'] = [];

    try {
      abortRef.current = new AbortController();

      const res = await fetch(`${API_BASE}/conversation/${sid}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
        signal: abortRef.current.signal,
      });

      if (!res.ok) throw new Error(`Request failed: ${res.statusText}`);
      if (!res.body) throw new Error('No response body');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const eventStr of events) {
          if (!eventStr.trim()) continue;

          const lines = eventStr.split('\n');
          let eventType = '';
          let eventData = '';

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7);
            } else if (line.startsWith('data: ')) {
              eventData = line.slice(6);
            }
          }

          if (!eventType || !eventData) continue;

          try {
            const data = JSON.parse(eventData);

            switch (eventType) {
              case 'token':
                fullText += data.text;
                setStreamingText(fullText);
                break;

              case 'sources':
                messageSources = data;
                setPendingSources(data);
                break;

              case 'url_context':
                messageUrlContexts = data;
                setPendingUrlContexts(data);
                // Also update the user message with URL contexts
                setMessages(prev => {
                  const updated = [...prev];
                  const lastUser = updated.findLastIndex(m => m.role === 'user');
                  if (lastUser >= 0) {
                    updated[lastUser] = { ...updated[lastUser], urlContexts: data };
                  }
                  return updated;
                });
                break;

              case 'done':
                setCurrentMode(data.mode || 'explore');
                // Add the complete assistant message
                setMessages(prev => [
                  ...prev,
                  {
                    role: 'assistant',
                    content: data.full_response,
                    mode: data.mode,
                    sources: messageSources,
                  },
                ]);
                setStreamingText('');
                break;

              case 'error':
                setError(data.message);
                break;
            }
          } catch {
            // Skip malformed JSON
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') return;
      setError(err instanceof Error ? err.message : 'Connection error');
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [sessionId, startSession]);

  const uploadMbz = useCallback(async (file: File) => {
    let sid = sessionId;
    if (!sid) {
      sid = await startSession();
      if (!sid) return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/conversation/${sid}/mbz`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Upload failed');
      }

      const data = await res.json();
      setMbzInfo(data.course);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    }
  }, [sessionId, startSession]);

  const uploadScreenshot = useCallback(async (file: File) => {
    let sid = sessionId;
    if (!sid) {
      sid = await startSession();
      if (!sid) return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/conversation/${sid}/screenshot`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Upload failed');
      }

      setPendingScreenshot(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Screenshot upload failed');
    }
  }, [sessionId, startSession]);

  const uploadHtml = useCallback(async (file: File) => {
    let sid = sessionId;
    if (!sid) {
      sid = await startSession();
      if (!sid) return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/conversation/${sid}/html`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Upload failed');
      }

      const data = await res.json();
      setHtmlPageInfo(data.page?.page_title || 'Page loaded');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'HTML upload failed');
    }
  }, [sessionId, startSession]);

  const newSession = useCallback(() => {
    setSessionId(null);
    setMessages([]);
    setStreamingText('');
    setCurrentMode('explore');
    setError(null);
    setMbzInfo(null);
    setPendingScreenshot(false);
    setHtmlPageInfo(null);
    if (abortRef.current) {
      abortRef.current.abort();
    }
  }, []);

  // Save session ID to localStorage whenever it changes
  useEffect(() => {
    if (sessionId && messages.length > 0) {
      const firstMsg = messages.find(m => m.role === 'user');
      const preview = firstMsg?.content?.slice(0, 80) || 'New session';

      try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        const updated = [
          { id: sessionId, preview, timestamp: Date.now() },
          ...stored.filter((s: any) => s.id !== sessionId),
        ].slice(0, 10); // Keep last 10
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      } catch {
        // localStorage unavailable
      }
    }
  }, [sessionId, messages.length]);

  // Restore a previous session
  const restoreSession = useCallback(async (sid: string) => {
    try {
      const res = await fetch(`${API_BASE}/conversation/${sid}`);
      if (!res.ok) {
        // Session expired — remove from recent list
        try {
          const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
          const updated = stored.filter((s: any) => s.id !== sid);
          localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
        } catch {}
        setError('Session expired. Starting a new one.');
        return false;
      }
      const data = await res.json();
      setSessionId(data.id);
      setMessages(data.messages || []);
      setError(null);

      // Detect current mode from last assistant message
      const lastAssistant = [...(data.messages || [])].reverse().find((m: any) => m.role === 'assistant');
      if (lastAssistant?.metadata?.mode) {
        setCurrentMode(lastAssistant.metadata.mode);
      }

      return true;
    } catch {
      setError('Could not restore session.');
      return false;
    }
  }, []);

  // Get recent sessions from localStorage
  const getRecentSessions = useCallback((): Array<{ id: string; preview: string; timestamp: number }> => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    } catch {
      return [];
    }
  }, []);

  return {
    sessionId,
    messages,
    streamingText,
    currentMode,
    isStreaming,
    error,
    mbzInfo,
    pendingSources,
    pendingUrlContexts,
    sendMessage,
    uploadMbz,
    uploadScreenshot,
    uploadHtml,
    pendingScreenshot,
    htmlPageInfo,
    newSession,
    startSession,
    restoreSession,
    getRecentSessions,
  };
}
