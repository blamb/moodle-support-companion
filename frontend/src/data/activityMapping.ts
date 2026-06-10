// Bloom's-taxonomy verb → suggested Moodle activities, and per-activity guidance.
// Ported from the LT&I "Moodle Activity Recommender" prototype. The recommender
// is deterministic and fully client-side: no backend, no API key, instant.

export const activityMapping: Record<string, string[]> = {
  identify: ['Quiz (Multiple Choice)', 'H5P (Image Hotspots)', 'Lesson', 'Choice'],
  recognize: ['Quiz (Matching)', 'H5P (Memory Game)', 'Lesson'],
  define: ['Glossary', 'Forum', 'Assignment', 'Wiki'],
  describe: ['Forum', 'Assignment', 'Lesson', 'Kaltura Media Assignment'],
  explain: ['Forum', 'Assignment', 'H5P (Course Presentation)', 'Lesson', 'Kaltura Media Assignment'],
  compare: ['Assignment', 'Forum', 'Wiki', 'Workshop', 'Database'],
  analyze: ['Assignment', 'Forum', 'Quiz (Essay)', 'Workshop', 'Database'],
  apply: ['Assignment', 'Quiz (Calculated)', 'H5P (Interactive Video)', 'SCORM package', 'Lesson'],
  solve: ['Assignment', 'Quiz (Numerical)', 'H5P (Drag and Drop)', 'Workshop'],
  interpret: ['Assignment', 'Forum', 'Quiz (Short Answer)', 'H5P (Image Sequencing)', 'Kaltura Media Assignment'],
  evaluate: ['Workshop', 'Feedback', 'Forum', 'Assignment', 'Survey'],
  design: ['Assignment', 'Wiki', 'Workshop', 'SCORM package', 'Database'],
  develop: ['Assignment', 'Wiki', 'Database', 'Kaltura Media Assignment', 'Workshop'],
  create: ['Assignment', 'Wiki', 'Database', 'H5P (Course Presentation)', 'Kaltura Media Assignment'],
  argue: ['Forum', 'Assignment', 'Workshop', 'Kaltura Media Assignment'],
  debate: ['Forum', 'Chat', 'Kaltura Media Assignment', 'Assignment'],
  justify: ['Forum', 'Assignment', 'Kaltura Media Assignment', 'Workshop'],
  critique: ['Workshop', 'Forum', 'Assignment', 'PDF Annotation'],
  collaborate: ['Forum', 'Wiki', 'Workshop', 'Group choice', 'Database', 'Chat'],
  reflect: ['Forum', 'Assignment', 'Feedback', 'Survey', 'Kaltura Media Assignment'],
  'self-assess': ['Quiz (Self-assessment)', 'Feedback', 'Survey', 'Workshop (with self-assessment enabled)'],
  participate: ['Forum', 'Chat', 'Attendance', 'Scheduler', 'Choice'],
  present: ['Kaltura Media Assignment', 'Assignment', 'Workshop', 'H5P (Course Presentation)', 'Lesson'],
  demonstrate: ['Kaltura Media Assignment', 'Assignment', 'H5P (Interactive Video)', 'SCORM package'],
  illustrate: ['Assignment', 'H5P (Image Hotspots)', 'Kaltura Media Assignment', 'Database'],
  summarize: ['Assignment', 'Forum', 'Wiki', 'Quiz (Short Answer)'],
  synthesize: ['Assignment', 'Wiki', 'Forum', 'Workshop', 'Database'],
  organize: ['Database', 'Wiki', 'Assignment', 'Glossary'],
  categorize: ['Database', 'Glossary', 'Quiz (Matching)', 'Wiki'],
  integrate: ['Assignment', 'Wiki', 'Workshop', 'SCORM package'],
  modify: ['Assignment', 'Wiki', 'Workshop', 'Database'],
  plan: ['Assignment', 'Wiki', 'Database', 'Forum'],
  propose: ['Assignment', 'Forum', 'Wiki', 'Kaltura Media Assignment'],
  formulate: ['Assignment', 'Forum', 'Quiz (Essay)', 'Workshop'],
  hypothesize: ['Assignment', 'Forum', 'Quiz (Essay)', 'Workshop'],
  predict: ['Assignment', 'Forum', 'Quiz (Multiple Choice)', 'H5P (Branching Scenario)'],
  assess: ['Workshop', 'Assignment', 'Quiz (True/False)', 'Feedback'],
  judge: ['Workshop', 'Forum', 'Assignment', 'Quiz (Essay)'],
  recommend: ['Assignment', 'Forum', 'Workshop', 'Kaltura Media Assignment'],
  review: ['PDF Annotation', 'Assignment', 'Workshop', 'Forum'],
  comment: ['PDF Annotation', 'Assignment', 'Forum', 'Feedback'],
  discuss: ['Forum', 'Chat', 'Kaltura Media Assignment', 'Assignment'],
  question: ['Forum', 'Quiz (Essay)', 'Assignment', 'Chat'],
  investigate: ['Assignment', 'Database', 'Forum', 'Wiki'],
  research: ['Assignment', 'Database', 'Wiki', 'Glossary'],
  explore: ['Assignment', 'H5P (Interactive Video)', 'SCORM package', 'Lesson'],
  experiment: ['Assignment', 'Workshop', 'H5P (Virtual Tour)', 'Database'],
  test: ['Quiz (Multiple Choice)', 'Assignment', 'H5P (Drag and Drop)', 'Workshop'],
  measure: ['Quiz (Numerical)', 'Assignment', 'Database', 'Survey'],
  calculate: ['Quiz (Calculated)', 'Assignment', 'H5P (Arithmetic Quiz)', 'Lesson'],
  construct: ['Assignment', 'Wiki', 'Database', 'Workshop'],
  build: ['Assignment', 'Wiki', 'Database', 'H5P (Course Presentation)'],
  assemble: ['Assignment', 'Wiki', 'Workshop', 'Database'],
  compose: ['Assignment', 'Wiki', 'Kaltura Media Assignment', 'Forum'],
  generate: ['Assignment', 'Database', 'Wiki', 'H5P (Dialog Cards)'],
  produce: ['Assignment', 'Kaltura Media Assignment', 'Workshop', 'Database'],
  revise: ['Assignment', 'Wiki', 'Workshop', 'PDF Annotation'],
  rewrite: ['Assignment', 'Wiki', 'Workshop', 'Forum'],
  simulate: ['SCORM package', 'H5P (Branching Scenario)', 'Assignment', 'Lesson'],
};

export interface ActivityDescription {
  justification: string;
  implementation: string;
}

// Keyed by the base activity name (the part before any parenthetical), so
// "Quiz (Multiple Choice)" and "Quiz (Essay)" share the "Quiz" guidance.
export const activityDescriptions: Record<string, ActivityDescription> = {
  Quiz: {
    justification: 'Quizzes provide immediate feedback and can assess understanding through various question types.',
    implementation:
      'Turn editing on → Add an activity or resource → Quiz → configure settings → Save and display → Edit quiz → add questions from the question bank or create new ones → set point values.',
  },
  H5P: {
    justification: 'H5P offers interactive content types that engage students and provide immediate feedback.',
    implementation:
      'Turn editing on → Add an activity or resource → Interactive Content (H5P) → upload or create content → choose a content type (Interactive Video, Course Presentation, Drag and Drop, etc.) → set grading options → Save and display.',
  },
  Lesson: {
    justification: 'Lessons allow for adaptive learning paths based on student responses.',
    implementation:
      'Turn editing on → Add an activity or resource → Lesson → configure settings → add content and question pages → create branching logic with jumps based on answers → preview the flow.',
  },
  Choice: {
    justification: 'Choice activities enable quick polling and decision-making exercises.',
    implementation:
      'Turn editing on → Add an activity or resource → Choice → enter the prompt → add options → set availability and limits → choose whether to publish results → Save and display.',
  },
  Glossary: {
    justification: 'Glossaries help students build vocabulary and can be collaboratively developed.',
    implementation:
      'Turn editing on → Add an activity or resource → Glossary → set display format and entry approval → enable auto-linking if desired → add initial entries or let students contribute → Save and display.',
  },
  Forum: {
    justification:
      'Forums promote discussion, collaboration, and critical thinking through asynchronous communication.',
    implementation:
      'Turn editing on → Add an activity or resource → Forum → choose forum type (Standard, Q&A, Single discussion) → set subscription/tracking → enable ratings or grading → Save and display.',
  },
  Assignment: {
    justification: 'Assignments allow for diverse submission types and provide opportunities for detailed feedback.',
    implementation:
      'Turn editing on → Add an activity or resource → Assignment → write clear instructions → set submission types and due dates → choose a grading method (points, rubric, marking guide) → configure feedback → Save and display.',
  },
  Wiki: {
    justification: 'Wikis facilitate collaborative content creation and knowledge building.',
    implementation:
      'Turn editing on → Add an activity or resource → Wiki → choose mode (collaborative or individual) → set the first page name and format → configure editing permissions → Save and display.',
  },
  Workshop: {
    justification: 'Workshops enable peer assessment and self-reflection through structured evaluation processes.',
    implementation:
      'Turn editing on → Add an activity or resource → Workshop → set up the assessment form (rubric/criteria) → define submission and assessment phases → set the grading strategy → allocate submissions for peer review.',
  },
  Database: {
    justification: 'Databases allow students to create, organize, and share structured information.',
    implementation:
      'Turn editing on → Add an activity or resource → Database → Save and display → add fields (text, file, date, menu) → customize templates → set permissions → configure ratings/comments.',
  },
  Feedback: {
    justification: 'Feedback activities gather anonymous responses and provide insights into student understanding.',
    implementation:
      'Turn editing on → Add an activity or resource → Feedback → set anonymous/non-anonymous → Edit questions → add items (multiple choice, text, numeric) → set availability → Save.',
  },
  Survey: {
    justification: 'Surveys collect structured data about student experiences and perspectives.',
    implementation:
      'Turn editing on → Add an activity or resource → Survey → choose a type (COLLES, ATTLS, or custom) → configure availability → Save and display.',
  },
  Chat: {
    justification: 'Chats enable real-time synchronous communication and quick exchanges.',
    implementation:
      'Turn editing on → Add an activity or resource → Chat → add a topic/guidelines → schedule sessions → set duration and log options → Save and display.',
  },
  Attendance: {
    justification: 'Attendance tracking helps monitor participation and engagement.',
    implementation:
      'Turn editing on → Add an activity or resource → Attendance → Save and display → Add session → set dates/times and status options (Present, Absent, Late, Excused) → take attendance → view reports.',
  },
  Scheduler: {
    justification: 'Schedulers facilitate one-on-one meetings and appointments.',
    implementation:
      'Turn editing on → Add an activity or resource → Scheduler → set booking mode and slot duration → add time slots → set max bookings per student → enable notifications → Save and display.',
  },
  'Kaltura Media Assignment': {
    justification: 'Media assignments enable video/audio submissions for presentations and demonstrations.',
    implementation:
      'Ensure Kaltura is integrated → Turn editing on → Add an activity or resource → Kaltura Media Assignment → write instructions → set submission limits and due dates → set up a grading rubric → Save and display.',
  },
  'PDF Annotation': {
    justification: 'PDF annotation tools enable detailed feedback and collaborative document review.',
    implementation:
      'Turn editing on → Add an activity or resource → Assignment → enable "Annotate PDF" in feedback types → upload the PDF → set submission/due dates → provide annotation guidelines → Save and display.',
  },
  'SCORM package': {
    justification: 'SCORM packages provide standardized interactive learning content with tracking capabilities.',
    implementation:
      'Turn editing on → Add an activity or resource → SCORM package → upload your .zip → set display (popup/embedded) → set grading method and passing grade → enable completion tracking → Save and display.',
  },
  'Group choice': {
    justification: 'Group choice activities facilitate team formation and collaborative work organization.',
    implementation:
      'Turn editing on → Add an activity or resource → Group choice → enter instructions → create options for each group/topic → set group size limits and dates → Save and display.',
  },
};

const STOPWORDS = new Set(['will', 'able', 'students', 'student', 'the', 'and', 'their', 'they']);

/** Find every Bloom's verb present in an objective, in order, de-duplicated. */
export function findVerbs(objective: string): string[] {
  const lower = objective.toLowerCase();
  const found: string[] = [];
  for (const verb of Object.keys(activityMapping)) {
    // Word-boundary match so "test" doesn't match "contest", etc.
    const re = new RegExp(`\\b${verb.replace('-', '\\-')}\\b`);
    if (re.test(lower) && !STOPWORDS.has(verb)) {
      found.push(verb);
    }
  }
  return found;
}

/** Look up guidance for an activity by its base name (before any parenthesis). */
export function describeActivity(activity: string): ActivityDescription {
  const base = activity.split('(')[0].trim();
  return (
    activityDescriptions[base] ?? {
      justification: 'A solid fit for this learning objective.',
      implementation: 'Configure the activity to match your course needs and assessment criteria.',
    }
  );
}
