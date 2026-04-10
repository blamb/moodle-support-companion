const MODE_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  explore: {
    label: 'EXPLORE',
    color: '#1d8cef',
    bg: '#e8f4fd',
    border: '#1d8cef',
  },
  diagnose: {
    label: 'DIAGNOSE',
    color: '#241c55',
    bg: '#f0eef7',
    border: '#241c55',
  },
  resolve: {
    label: 'RESOLVE',
    color: '#00b18f',
    bg: '#e6f7f4',
    border: '#00b18f',
  },
};

interface ModeBadgeProps {
  mode: string;
}

export function ModeBadge({ mode }: ModeBadgeProps) {
  const config = MODE_CONFIG[mode] || MODE_CONFIG.explore;

  return (
    <span
      className="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-bold uppercase tracking-wider border"
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
