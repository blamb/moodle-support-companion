import { useState, useRef, useEffect } from 'react';

interface MessageInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
  placeholder?: string;
}

export function MessageInput({ onSend, disabled, placeholder }: MessageInputProps) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    }
  }, [text]);

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (trimmed && !disabled) {
      onSend(trimmed);
      setText('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const hasMoodleUrl = /moodle\.tru\.ca/.test(text);

  return (
    <div className="border-t border-slate-200 bg-white p-4 rounded-b-xl">
      <div className="flex gap-3 items-end">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            rows={1}
            placeholder={placeholder || "Describe the issue, paste a Moodle URL, or respond to questions..."}
            className="w-full resize-none rounded-lg border border-slate-200 px-4 py-3
                       text-sm focus:outline-none focus:ring-2
                       focus:border-transparent disabled:bg-slate-50 disabled:text-slate-400
                       placeholder:text-slate-400"
            style={{ '--tw-ring-color': 'var(--lti-purple)' } as any}
          />
          {hasMoodleUrl && (
            <div className="absolute right-3 top-3">
              <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                style={{ backgroundColor: 'var(--lti-gold-light)', color: 'var(--lti-gold-hover)' }}>
                Moodle URL detected
              </span>
            </div>
          )}
        </div>
        <button
          onClick={handleSubmit}
          disabled={disabled || !text.trim()}
          className="lti-btn-gold flex-shrink-0 text-sm"
        >
          {disabled ? (
            <div className="h-5 w-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            'Send'
          )}
        </button>
      </div>
      <p className="text-xs text-slate-400 mt-1 ml-1">
        Press Enter to send, Shift+Enter for new line
      </p>
    </div>
  );
}
