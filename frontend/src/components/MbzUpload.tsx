import { useRef } from 'react';

interface MbzInfo {
  course_name: string;
  activity_count: number;
  activity_types: string[];
  summary: string;
}

interface MbzUploadProps {
  onUpload: (file: File) => void;
  onScreenshot: (file: File) => void;
  onHtmlUpload: (file: File) => void;
  mbzInfo: MbzInfo | null;
  pendingScreenshot: boolean;
  htmlPageInfo: string | null;
}

export function MbzUpload({ onUpload, onScreenshot, onHtmlUpload, mbzInfo, pendingScreenshot, htmlPageInfo }: MbzUploadProps) {
  const mbzInputRef = useRef<HTMLInputElement>(null);
  const screenshotInputRef = useRef<HTMLInputElement>(null);
  const htmlInputRef = useRef<HTMLInputElement>(null);

  const handleMbzChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onUpload(file);
    e.target.value = '';
  };

  const handleScreenshotChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onScreenshot(file);
    e.target.value = '';
  };

  const handleHtmlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onHtmlUpload(file);
    e.target.value = '';
  };

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {/* Hidden inputs */}
      <input ref={mbzInputRef} type="file" accept=".mbz" onChange={handleMbzChange} className="hidden" aria-label="Upload Moodle course backup (.mbz)" />
      <input ref={screenshotInputRef} type="file" accept="image/*" onChange={handleScreenshotChange} className="hidden" aria-label="Upload screenshot image" />
      <input ref={htmlInputRef} type="file" accept=".html,.htm" onChange={handleHtmlChange} className="hidden" aria-label="Upload saved Moodle HTML page" />

      {/* MBZ info or upload button */}
      {mbzInfo ? (
        <div className="text-xs rounded-lg px-3 py-1.5 border" role="status"
             style={{ backgroundColor: 'var(--lti-teal-light)', borderColor: 'var(--lti-teal)', color: 'var(--lti-teal)' }}>
          <span className="font-medium">{mbzInfo.course_name}</span>
          <span className="opacity-70 ml-1">({mbzInfo.activity_count} activities)</span>
        </div>
      ) : (
        <button
          onClick={() => mbzInputRef.current?.click()}
          className="lti-btn-outline flex items-center gap-1.5"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          .mbz backup
        </button>
      )}

      {/* Screenshot button */}
      <button
        onClick={() => screenshotInputRef.current?.click()}
        className="lti-btn-outline flex items-center gap-1.5"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        Screenshot
        {pendingScreenshot && (
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: 'var(--lti-gold)' }} />
        )}
      </button>

      {/* HTML page button */}
      <button
        onClick={() => htmlInputRef.current?.click()}
        className="lti-btn-outline flex items-center gap-1.5"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
        </svg>
        Saved page
      </button>

      {/* HTML page info */}
      {htmlPageInfo && (
        <span className="text-xs rounded-lg px-2 py-1 border" role="status"
              style={{ backgroundColor: 'var(--lti-blue-light)', borderColor: 'var(--lti-blue)', color: 'var(--lti-blue)' }}>
          {htmlPageInfo}
        </span>
      )}

      {/* Pending screenshot indicator */}
      {pendingScreenshot && (
        <span className="text-xs rounded-lg px-2 py-1 border" role="status"
              style={{ backgroundColor: 'var(--lti-gold-light)', borderColor: 'var(--lti-gold)', color: '#b45309' }}>
          Screenshot ready — will be sent with next message
        </span>
      )}
    </div>
  );
}
