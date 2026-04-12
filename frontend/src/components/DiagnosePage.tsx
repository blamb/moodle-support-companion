import { useRef, useEffect, useState } from 'react';
import { useConversation } from '../hooks/useConversation';
import { ChatMessage } from './ChatMessage';
import { MessageInput } from './MessageInput';
import { MbzUpload } from './MbzUpload';
import { ModeBadge } from './ModeBadge';
import { SaveCaseDialog } from './SaveCaseDialog';
import { DraftReplyDialog } from './DraftReplyDialog';

interface DiagnosePageProps {
  initialMessage?: string | null;
  onInitialMessageConsumed?: () => void;
  sharedSessionId?: string | null;
  onSharedSessionConsumed?: () => void;
}

export function DiagnosePage({ initialMessage, onInitialMessageConsumed, sharedSessionId, onSharedSessionConsumed }: DiagnosePageProps) {
  const {
    sessionId,
    messages,
    streamingText,
    currentMode,
    isStreaming,
    error,
    mbzInfo,
    pendingSources,
    sendMessage,
    uploadMbz,
    uploadScreenshot,
    uploadHtml,
    pendingScreenshot,
    htmlPageInfo,
    newSession,
    restoreSession,
    getRecentSessions,
  } = useConversation();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [showDraftDialog, setShowDraftDialog] = useState(false);
  const [savedCaseId, setSavedCaseId] = useState<string | null>(null);
  const [followUpDismissed, setFollowUpDismissed] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText]);

  // Handle shared session link
  useEffect(() => {
    if (sharedSessionId) {
      restoreSession(sharedSessionId);
      onSharedSessionConsumed?.();
    }
  }, [sharedSessionId]);

  // Handle initial message from Search tab
  useEffect(() => {
    if (initialMessage && !isStreaming) {
      sendMessage(initialMessage);
      onInitialMessageConsumed?.();
    }
  }, [initialMessage]);

  // Reset follow-up dismissed when starting new session
  useEffect(() => {
    if (messages.length === 0) {
      setFollowUpDismissed(false);
    }
  }, [messages.length]);

  const handleSaved = (caseId: string) => {
    setSavedCaseId(caseId);
    setShowSaveDialog(false);
  };

  const handleShare = async () => {
    if (!sessionId) return;
    try {
      const res = await fetch(`/api/conversation/${sessionId}/share`, { method: 'POST' });
      if (!res.ok) throw new Error('Share failed');
      const data = await res.json();
      const link = `${window.location.origin}?shared=${data.share_id}`;
      await navigator.clipboard.writeText(link);
      setShareCopied(true);
      setTimeout(() => setShareCopied(false), 3000);
    } catch {
      // Silently fail
    }
  };

  const handleExport = async () => {
    if (!sessionId) return;
    try {
      const res = await fetch(`/api/conversation/${sessionId}/export`);
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `diagnostic-session-${sessionId.slice(0, 8)}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // Silently fail — the error display will catch API issues
    }
  };

  // Determine if we should show the follow-up prompt
  const showFollowUp = !followUpDismissed &&
    !isStreaming &&
    !savedCaseId &&
    currentMode === 'resolve' &&
    messages.length >= 2 &&
    messages[messages.length - 1]?.role === 'assistant';

  // Better error messages
  const getErrorMessage = (err: string) => {
    if (err.includes('Failed to fetch') || err.includes('Connection error') || err.includes('NetworkError')) {
      return 'Cannot connect to the backend. Is the server running? Start it with: python3 -m uvicorn app.main:app --port 8000';
    }
    if (err.includes('401') || err.includes('authentication') || err.includes('api_key') || err.includes('auth_token')) {
      return 'API key not set or invalid. Set it with: export ANTHROPIC_API_KEY="your-key" then restart the backend.';
    }
    if (err.includes('429') || err.includes('rate_limit')) {
      return 'Rate limit reached. Wait a moment and try again.';
    }
    if (err.includes('500') || err.includes('Internal')) {
      return 'Backend error. Check the terminal running the backend for details.';
    }
    if (err.includes('404') || err.includes('not found') || err.includes('Not found')) {
      return 'Endpoint not found. You may need to restart the backend to load new code: stop it (Ctrl+C) and run python3 -m uvicorn app.main:app --port 8000 --reload';
    }
    return err;
  };

  return (
    <div className="flex flex-col h-[calc(100vh-120px)]">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <div className="flex items-center gap-3">
          <ModeBadge mode={currentMode} />
          <MbzUpload
            onUpload={uploadMbz}
            onScreenshot={uploadScreenshot}
            onHtmlUpload={uploadHtml}
            mbzInfo={mbzInfo}
            pendingScreenshot={pendingScreenshot}
            htmlPageInfo={htmlPageInfo}
          />
        </div>
        <div className="flex items-center gap-2">
          {sessionId && messages.length > 0 && (
            <>
              <button onClick={handleExport} className="lti-btn-outline" title="Export as Markdown">
                Export
              </button>
              <button
                onClick={handleShare}
                className="lti-btn-outline"
                title="Share with a colleague"
                aria-label={shareCopied ? 'Link copied to clipboard' : 'Share conversation'}
              >
                {shareCopied ? '✓ Copied!' : 'Share'}
              </button>
              <button onClick={() => setShowDraftDialog(true)} className="lti-btn-outline">
                Draft Reply
              </button>
              <button onClick={() => setShowSaveDialog(true)} disabled={!sessionId} className="lti-btn-outline">
                Save as Case
              </button>
              {savedCaseId && (
                <span className="text-xs text-emerald-600" role="status">Saved</span>
              )}
            </>
          )}
          <button
            onClick={() => {
              newSession();
              setSavedCaseId(null);
            }}
            className="lti-btn-outline"
          >
            New Session
          </button>
        </div>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto bg-slate-50 rounded-xl border border-slate-200 p-4">
        {messages.length === 0 && !streamingText ? (
          <div className="flex items-center justify-center h-full text-slate-500">
            <div className="text-center">
              <svg className="mx-auto h-12 w-12 mb-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              <p className="text-lg font-medium">Ready to diagnose</p>
              <p className="text-sm mt-1">
                Describe the support issue, paste a Moodle URL, or upload a course backup
              </p>
              <div className="mt-4 text-xs text-slate-500 max-w-sm mx-auto">
                <p className="mb-1">Try something like:</p>
                <p className="italic">"A teacher reports that students can't see their quiz grades after completing the quiz. The course is HEAL_1150."</p>
              </div>

              {/* Recent sessions */}
              {(() => {
                const recent = getRecentSessions();
                if (recent.length === 0) return null;
                return (
                  <div className="mt-6 text-left max-w-sm mx-auto">
                    <p className="text-xs font-medium text-slate-500 mb-2">Recent sessions:</p>
                    <div className="space-y-1">
                      {recent.slice(0, 5).map((s) => (
                        <button
                          key={s.id}
                          onClick={() => restoreSession(s.id)}
                          className="w-full text-left text-xs text-slate-500 hover:text-orange-600
                                     bg-white border border-slate-200 hover:border-orange-300
                                     rounded-lg px-3 py-2 transition-colors truncate"
                        >
                          {s.preview}
                          <span className="text-slate-300 ml-2">
                            {new Date(s.timestamp).toLocaleDateString()}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <ChatMessage
                key={i}
                role={msg.role}
                content={msg.content}
                mode={msg.mode}
                sources={msg.sources}
                urlContexts={msg.urlContexts}
              />
            ))}
            {/* Streaming message */}
            {streamingText && (
              <ChatMessage
                role="assistant"
                content={streamingText}
                mode={currentMode}
                sources={pendingSources || undefined}
                isStreaming={true}
              />
            )}

            {/* Follow-up prompt after resolution */}
            {showFollowUp && (
              <div className="mt-4 rounded-xl p-4 border"
                   style={{ backgroundColor: 'var(--lti-gold-light)', borderColor: 'var(--lti-gold)' }}>
                <p className="text-sm font-medium mb-2" style={{ color: 'var(--lti-navy)' }}>
                  Issue resolved? Consider these next steps:
                </p>
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => setShowSaveDialog(true)} className="lti-btn-gold text-xs">
                    Save as Case
                  </button>
                  <button onClick={() => setShowDraftDialog(true)} className="lti-btn-outline">
                    Draft Reply
                  </button>
                  <button onClick={handleExport} className="lti-btn-outline">
                    Export for training
                  </button>
                  <button
                    onClick={() => sendMessage("Would this issue be worth documenting in our FAQ or knowledge base? If so, draft a short knowledge base article.")}
                    className="lti-btn-outline"
                  >
                    Draft KB article
                  </button>
                  <button
                    onClick={() => setFollowUpDismissed(true)}
                    className="text-xs px-2 py-1.5 transition-colors"
                    style={{ color: 'var(--lti-charcoal)', opacity: 0.5 }}
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Visually-hidden live region for streaming status */}
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {isStreaming ? 'Assistant is responding...' : ''}
        {error ? `Error: ${getErrorMessage(error)}` : ''}
      </div>

      {/* Error display — with actionable messages */}
      {error && (
        <div className="mt-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700" role="alert">
          <p className="font-medium">Something went wrong</p>
          <p className="text-xs mt-1">{getErrorMessage(error)}</p>
        </div>
      )}

      {/* Input area */}
      <MessageInput onSend={sendMessage} disabled={isStreaming} />

      {/* Dialogs */}
      {showSaveDialog && sessionId && (
        <SaveCaseDialog
          sessionId={sessionId}
          onClose={() => setShowSaveDialog(false)}
          onSaved={handleSaved}
        />
      )}
      {showDraftDialog && sessionId && (
        <DraftReplyDialog
          sessionId={sessionId}
          onClose={() => setShowDraftDialog(false)}
        />
      )}
    </div>
  );
}
