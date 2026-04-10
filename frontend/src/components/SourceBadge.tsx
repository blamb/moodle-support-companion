const SOURCE_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  moodle_docs: {
    label: 'Moodle Docs',
    color: '#b45309',
    bg: '#fef3c7',
    border: '#f59e0b',
  },
  olproduction: {
    label: 'OL Production',
    color: '#1d8cef',
    bg: '#e8f4fd',
    border: '#1d8cef',
  },
  trubox: {
    label: 'TRU Box',
    color: '#00b18f',
    bg: '#e6f7f4',
    border: '#00b18f',
  },
  tru_faq: {
    label: 'TRU FAQ',
    color: '#9333ea',
    bg: '#f3e8ff',
    border: '#a855f7',
  },
};

interface SourceBadgeProps {
  source: string;
}

export function SourceBadge({ source }: SourceBadgeProps) {
  const config = SOURCE_CONFIG[source] || {
    label: source,
    color: '#64748b',
    bg: '#f1f5f9',
    border: '#94a3b8',
  };

  return (
    <span
      className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium border"
      style={{
        color: config.color,
        backgroundColor: config.bg,
        borderColor: config.border,
      }}
    >
      {config.label}
    </span>
  );
}
