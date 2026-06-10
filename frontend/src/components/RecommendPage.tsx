import { useState } from 'react';
import { activityMapping, findVerbs, describeActivity } from '../data/activityMapping';

interface Recommendation {
  objective: string;
  verbs: string[];
  activities: string[];
}

const DEFAULT_ACTIVITIES = ['Assignment', 'Forum', 'Quiz (Multiple Choice)'];
const MAX_ACTIVITIES = 4;

function buildRecommendations(objectives: string[]): Recommendation[] {
  return objectives.map((objective) => {
    const verbs = findVerbs(objective);
    // Merge the activity lists for every matched verb, in order, de-duplicated.
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
  const [results, setResults] = useState<Recommendation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const updateObjective = (i: number, value: string) => {
    setObjectives((prev) => prev.map((o, idx) => (idx === i ? value : o)));
  };
  const addObjective = () => setObjectives((prev) => [...prev, '']);
  const removeObjective = (i: number) =>
    setObjectives((prev) => (prev.length > 1 ? prev.filter((_, idx) => idx !== i) : prev));

  const generate = () => {
    const filled = objectives.map((o) => o.trim()).filter(Boolean);
    if (filled.length === 0) {
      setError('Enter at least one learning objective.');
      setResults(null);
      return;
    }
    setError(null);
    setResults(buildRecommendations(filled));
  };

  const copyResults = async () => {
    if (!results) return;
    const lines: string[] = [];
    const header = [courseName, courseLevel, courseArea].filter(Boolean).join(' · ');
    if (header) lines.push(header, '');
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
          Enter course learning objectives and get Moodle activity suggestions based on the{' '}
          Bloom&apos;s-taxonomy verbs they contain — with a justification and setup steps for each.
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

        {error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700" role="alert">
            {error}
          </div>
        )}

        <button onClick={generate} className="lti-btn-gold mt-4 w-full">
          Generate recommendations
        </button>
      </div>

      {/* Results */}
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
    </div>
  );
}
