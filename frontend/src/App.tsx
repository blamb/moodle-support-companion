import { useState, useCallback, useEffect } from 'react';
import { SearchPage } from './components/SearchPage';
import { DiagnosePage } from './components/DiagnosePage';
import { CasesPage } from './components/CasesPage';
import './index.css';

type Tab = 'diagnose' | 'search' | 'cases';

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('diagnose');
  const [diagnoseInitialMessage, setDiagnoseInitialMessage] = useState<string | null>(null);
  const [sharedSessionId, setSharedSessionId] = useState<string | null>(null);

  // Check for shared conversation link on load
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const shareId = params.get('shared');
    if (shareId) {
      fetch(`/api/shared/${shareId}`)
        .then(res => {
          if (!res.ok) throw new Error('Not found');
          return res.json();
        })
        .then(data => {
          setSharedSessionId(data.id);
          setActiveTab('diagnose');
          // Clean the URL
          window.history.replaceState({}, '', window.location.pathname);
        })
        .catch(() => {
          // Invalid share link — just ignore
          window.history.replaceState({}, '', window.location.pathname);
        });
    }
  }, []);

  const handleStartDiagnosis = useCallback((text: string) => {
    setDiagnoseInitialMessage(text);
    setActiveTab('diagnose');
  }, []);

  const handleDiagnoseMessageConsumed = useCallback(() => {
    setDiagnoseInitialMessage(null);
  }, []);

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--lti-gray-light)' }}>
      {/* Gold accent bar */}
      <div className="lti-gold-bar" />

      {/* Header — white with logo, matching LT&I site */}
      <header className="bg-white shadow-sm">
        <div className="max-w-6xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            {/* Left: Logo + Title */}
            <div className="flex items-center gap-4">
              <img
                src="/lti-logo.png"
                alt="LT&I"
                className="h-9"
              />
              <div className="hidden sm:block">
                <p className="text-xs font-semibold uppercase tracking-widest"
                   style={{ color: 'var(--lti-gold)' }}>
                  Thompson Rivers University
                </p>
                <h1 className="text-lg font-bold leading-tight"
                    style={{ color: 'var(--lti-navy)' }}>
                  Moodle Support Companion
                </h1>
              </div>
            </div>

            {/* Right: Tab switcher */}
            <nav className="flex items-center gap-1 rounded-lg p-1"
                 style={{ backgroundColor: 'var(--lti-purple-light)' }}>
              {([
                { key: 'diagnose', label: 'Diagnose', icon: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z' },
                { key: 'search', label: 'Search', icon: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z' },
                { key: 'cases', label: 'Cases', icon: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10' },
              ] as const).map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-all"
                  style={{
                    backgroundColor: activeTab === tab.key ? 'var(--lti-purple)' : 'transparent',
                    color: activeTab === tab.key ? 'white' : 'var(--lti-navy)',
                  }}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={tab.icon} />
                  </svg>
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-6xl mx-auto px-4 py-6">
        {activeTab === 'diagnose' && (
          <DiagnosePage
            initialMessage={diagnoseInitialMessage}
            onInitialMessageConsumed={handleDiagnoseMessageConsumed}
            sharedSessionId={sharedSessionId}
            onSharedSessionConsumed={() => setSharedSessionId(null)}
          />
        )}
        {activeTab === 'search' && (
          <SearchPage onStartDiagnosis={handleStartDiagnosis} />
        )}
        {activeTab === 'cases' && <CasesPage />}
      </main>
    </div>
  );
}

export default App;
