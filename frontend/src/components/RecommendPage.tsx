import { useState } from 'react';
import { activityMapping, findVerbs, describeActivity } from '../data/activityMapping';

interface Recommendation {
  objective: string;
  verbs: string[];
  activities: string[];
}

interface AIIdea {
  activity: string;
  why: string;
  how: string;
  underused: boolean;
}
interface AISuggestion {
  objective: string;
  ideas: AIIdea[];
}
interface AIData {
  suggestions: AISuggestion[];
  note: string;
}

const DEFAULT_ACTIVITIES = ['Assignment', 'Forum', 'Quiz (Multiple Choice)'];
const MAX_ACTIVITIES = 4;

function buildRecommendations(objectives: string[]): Recommendation[] {
  return objectives.map((objective) => {
    const verbs = findVerbs(objective);
    const merged: string[] = [];
    for (const verb of verbs) {
      for (const activity of activityMapping[verb]) {
        if (!merged.includes(activity)) merged.push(activity);
      }
    }
    const activities = (merged.length ? merged : DEFAULT_ACTIVITIES).slice(0, MAX_ACTIVITIES);
    return { objective, verbs, activities };
  });
}

export function RecommendPage() {
  const [courseName, setCourseName] = useState('');
  const [courseLevel, setCourseLevel] = useState('');
  const [courseArea, setCourseArea] = useState('');
  const [objectives, setObjectives] = useState<string[]>(['']);
  const [aiMode, setAiMode] = useState(false);
  const [results, setResults] = useState<Recommendation[] | null>(null);
  const [aiData, setAiData] = useState<AIData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const updateObjective = (i: number, value: string) => {
    setObjectives((prev) => prev.map((o, idx) => (idx === i ? value : o)));
  };
  const addObjective = () => setObjectives((prev) => [...prev, '']);
  const removeObjective = (i: number) =>
    setObjectives((prev) => (prev.length > 1 ? prev.filter((_, idx) => idx !== i) : prev));

  const generate = async () => {
    const filled = objectives.map((o) => o.trim()).filter(Boolean);
    if (filled.length === 0) {
      setError('Enter at least one learning objective.');
      setResults(null);
      setAiData(null);
      return;
    }
    setError(null);

    if (!aiMode) {
      setAiData(null);
      setResults(buildRecommendations(filled));
      return;
    }

    // AI mode — tailored suggestions from the backend.
    setLoading(true);
    setResults(null);
    try {
      const res = await fetch('/api/activities/suggest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          objectives: filled,
          course_name: courseName,
          course_level: courseLevel,
          course_area: courseArea,
        }),
      });
      if (!res.ok) {
        let detail = `Request failed (${res.status})`;
        try {
          const b = await res.json();
          if (b?.detail) detail = b.detail;
        } catch {
          /* keep default */
        }
        throw new Error(detail);
      }
      const data: AIData = await res.json();
      setAiData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get AI ideas.');
      setAiData(null);
    } finally {
      setLoading(false);
    }
  };

  const copyResults = async () => {
    const lines: string[] = [];
    const header = [courseName, courseLevel, courseArea].filter(Boolean).join(' · ');
    if (header) lines.push(header, '');

    if (aiData) {
      if (aiData.note) lines.push(aiData.note, '');
      aiData.suggestions.forEach((s, i) => {
        lines.push(`Objective ${i + 1}: ${s.objective}`);
        s.ideas.forEach((idea) => {
          lines.push(`  • ${idea.activity}${idea.underused ? ' (under-used)' : ''} — ${idea.why}`);
          lines.push(`    How: ${idea.how}`);
        });
        lines.push('');
      });
    } else if (results) {
      results.forEach((r, i) => {
        lines.push(`Objective ${i + 1}: ${r.objective}`);
        if (r.verbs.length) lines.push(`Bloom's verbs: ${r.verbs.join(', ')}`);
        r.activities.forEach((a) => {
          const d = describeActivity(a);
          lines.push(`  • ${a} — ${d.justification}`);
          lines.push(`    How: ${d.implementation}`);
        });
        lines.push('');
      });
    } else {
      return;
    }

    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="space-y-5">
      {/* Intro */}
      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <h2 className="text-lg font-bold mb-1" style={{ color: 'var(--lti-navy)' }}>
          Activity Recommender
        </h2>
        <p className="text-sm text-slate-600">
          Turn course learning objectives into Moodle activity suggestions. The{' '}
          <strong>Bloom&apos;s map</strong> is instant and offline; <strong>AI ideas</strong> gives
          tailored, course-specific suggestions that deliberately surface effective but under-used
          activities — to help instructors move beyond just quizzes, assignments, and forums.
        </p>
      </div>

      {/* Course info (optional) */}
      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <h3 className="text-sm font-medium text-slate-700 mb-3">Course information (optional)</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <input
            value={courseName}
            onChange={(e) => setCourseName(e.target.value)}
            placeholder="Course name"
            className="p-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-[#2d1b69]"
          />
          <input
            value={courseLevel}
            onChange={(e) => setCourseLevel(e.target.value)}
            placeholder="Level (e.g. Undergraduate)"
            className="p-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-[#2d1b69]"
          />
          <input
            value={courseArea}
            onChange={(e) => setCourseArea(e.target.value)}
            placeholder="Area (e.g. Engineering)"
            className="p-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-[#2d1b69]"
          />
        </div>
      </div>

      {/* Objectives */}
      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <h3 className="text-sm font-medium text-slate-700 mb-3">Learning objectives</h3>
        <div className="space-y-2.5">
          {objectives.map((obj, i) => (
            <div key={i} className="flex gap-2">
              <textarea
                value={obj}
                onChange={(e) => updateObjective(i, e.target.value)}
                rows={2}
                placeholder={`Objective ${i + 1}: e.g. "Students will be able to analyze statistical data…"`}
                className="flex-1 p-2.5 border border-slate-300 rounded-lg text-sm resize-y
                           focus:outline-none focus:border-[#2d1b69] focus:ring-2 focus:ring-[#2d1b69]/10"
              />
              {objectives.length > 1 && (
                <button
                  onClick={() => removeObjective(i)}
                  aria-label={`Remove objective ${i + 1}`}
                  className="px-2 text-slate-300 hover:text-red-500 transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              )}
            </div>
          ))}
        </div>
        <button
          onClick={addObjective}
          className="mt-3 text-sm font-medium flex items-center gap-1"
          style={{ color: 'var(--lti-purple-mid)' }}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Add another objective
        </button>

        {/* Suggestion style */}
        <div className="mt-4">
          <p className="text-xs font-medium text-slate-500 mb-1.5">Suggestion style</p>
          <div className="flex flex-wrap gap-2">
            {([
              { key: false, label: "Bloom's map", hint: 'Instant, offline, verb-based' },
              { key: true, label: 'AI ideas', hint: 'Tailored & course-specific (uses Claude)' },
            ] as const).map((m) => (
              <button
                key={String(m.key)}
                onClick={() => setAiMode(m.key)}
                title={m.hint}
                className={`px-3 py-1.5 rounded-md text-sm font-medium border transition-colors ${
                  aiMode === m.key
                    ? 'text-white border-transparent'
                    : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
                }`}
                style={aiMode === m.key ? { backgroundColor: 'var(--lti-purple)' } : undefined}
              >
                {m.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-slate-400 mt-1.5">
            {aiMode
              ? 'Tailored, course-specific ideas that surface under-used activities.'
              : 'Instant suggestions from a Bloom’s-verb → activity map. No AI.'}
          </p>
        </div>

        {error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700" role="alert">
            {error}
          </div>
        )}

        <button onClick={generate} disabled={loading} className="lti-btn-gold mt-4 w-full">
          {loading ? 'Thinking…' : aiMode ? 'Get AI ideas' : 'Generate recommendations'}
        </button>
      </div>

      {/* Bloom's-map results */}
      {results && (
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-bold" style={{ color: 'var(--lti-navy)' }}>
              Recommendations
            </h3>
            <button onClick={copyResults} className="lti-btn-outline">
              {copied ? 'Copied!' : 'Copy all'}
            </button>
          </div>

          <div className="space-y-5">
            {results.map((r, i) => (
              <div key={i}>
                <div className="rounded px-3 py-2 mb-2 border-l-4"
                     style={{ backgroundColor: 'var(--lti-purple-light)', borderColor: 'var(--lti-purple)' }}>
                  <p className="text-sm font-medium text-slate-800">
                    <span className="text-slate-500">Objective {i + 1}:</span> {r.objective}
                  </p>
                  {r.verbs.length > 0 ? (
                    <p className="text-xs text-slate-500 mt-1">
                      Bloom&apos;s verb{r.verbs.length > 1 ? 's' : ''}:{' '}
                      <span className="font-medium">{r.verbs.join(', ')}</span>
                    </p>
                  ) : (
                    <p className="text-xs text-amber-600 mt-1">
                      No Bloom&apos;s verb detected — showing general-purpose activities.
                    </p>
                  )}
                </div>

                <div className="space-y-3 pl-3 border-l-2 border-slate-100">
                  {r.activities.map((activity) => {
                    const d = describeActivity(activity);
                    return (
                      <div key={activity} className="pl-2">
                        <p className="font-semibold text-sm" style={{ color: 'var(--lti-purple-mid)' }}>
                          {activity}
                        </p>
                        <p className="text-xs text-slate-600 mt-0.5">
                          <span className="font-medium text-slate-700">Why:</span> {d.justification}
                        </p>
                        <p className="text-xs text-slate-500 mt-0.5">
                          <span className="font-medium text-slate-700">How:</span> {d.implementation}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI ideas results */}
      {aiData && (
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold" style={{ color: 'var(--lti-navy)' }}>
                Tailored ideas
              </h3>
              <span className="text-xs px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200">
                AI-assisted
              </span>
            </div>
            <button onClick={copyResults} className="lti-btn-outline">
              {copied ? 'Copied!' : 'Copy all'}
            </button>
          </div>

          {aiData.note && (
            <div className="mb-4 p-3 bg-purple-50 border border-purple-200 rounded-lg text-sm text-purple-800">
              {aiData.note}
            </div>
          )}

          <div className="space-y-5">
            {aiData.suggestions.map((s, i) => (
              <div key={i}>
                <div className="rounded px-3 py-2 mb-2 border-l-4"
                     style={{ backgroundColor: 'var(--lti-purple-light)', borderColor: 'var(--lti-purple)' }}>
                  <p className="text-sm font-medium text-slate-800">
                    <span className="text-slate-500">Objective {i + 1}:</span> {s.objective}
                  </p>
                </div>

                <div className="space-y-3 pl-3 border-l-2 border-slate-100">
                  {s.ideas.map((idea, j) => (
                    <div key={j} className="pl-2">
                      <p className="font-semibold text-sm flex items-center gap-2"
                         style={{ color: 'var(--lti-purple-mid)' }}>
                        {idea.activity}
                        {idea.underused && (
                          <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded
                                           bg-teal-50 text-teal-700 border border-teal-200">
                            under-used
                          </span>
                        )}
                      </p>
                      {idea.why && (
                        <p className="text-xs text-slate-600 mt-0.5">
                          <span className="font-medium text-slate-700">Why:</span> {idea.why}
                        </p>
                      )}
                      {idea.how && (
                        <p className="text-xs text-slate-500 mt-0.5">
                          <span className="font-medium text-slate-700">How:</span> {idea.how}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <p className="text-xs text-slate-400 mt-4">
            AI suggestions are a starting point — adapt them to your course and learners.
          </p>
        </div>
      )}
    </div>
  );
}
