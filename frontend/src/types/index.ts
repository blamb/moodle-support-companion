export interface SearchResult {
  text: string;
  score: number;
  source: string;
  title: string;
  categories: string[];
  canonical_url: string | null;
  chunk_index: number;
  total_chunks: number;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
}

export interface SourceStats {
  source: string;
  document_count: number;
  chunk_count: number;
}

export interface SourcesResponse {
  sources: SourceStats[];
  total_chunks: number;
}

// Conversation types
export interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
  mode?: string;
  sources?: Array<{
    title: string;
    source: string;
    canonical_url?: string;
    score?: number;
  }>;
  urlContexts?: Array<{
    context_summary: string;
    url: string;
    module_type?: string;
    course_id?: number;
  }>;
}

export interface MbzInfo {
  course_name: string;
  activity_count: number;
  activity_types: string[];
  summary: string;
}

// Question import types
export interface QImportOption {
  text: string;
  fraction: number;
  feedback: string;
}

export interface QImportAnswer {
  text: string;
  fraction: number;
  tolerance?: number;
}

export interface QImportPair {
  question: string;
  answer: string;
}

export interface ParsedQuestion {
  number: number;
  qtype: string;
  type_label: string;
  text: string;
  name: string;
  single: boolean;
  options: QImportOption[];
  answers: QImportAnswer[];
  pairs: QImportPair[];
  correct: string | null;
  feedback: string;
  warnings: string[];
}

export interface ParseSummary {
  total: number;
  by_type: Record<string, number>;
  needs_review: number;
  unparsed: number;
}

export interface QuestionExports {
  gift: string;
  xml: string;
  aiken: string;
  aiken_skipped: string[];
}

export interface ParseResponse {
  questions: ParsedQuestion[];
  warnings: string[];
  unparsed: Array<{ text: string; reason: string }>;
  used_ai: boolean;
  summary: ParseSummary;
  exports: QuestionExports;
}

export type ImportMode = 'auto' | 'rules' | 'ai';
export type ExportFormat = 'gift' | 'xml' | 'aiken';

export interface CaseRecord {
  id: string;
  created_at: number;
  updated_at: number;
  summary: string;
  problem_description: string;
  diagnosis: string;
  resolution: string;
  tags: string[];
  difficulty: number;
  moodle_module: string;
  course_id: string;
  status: string;
  conversation?: ConversationMessage[];
}
