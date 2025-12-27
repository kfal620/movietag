type Props = {
  title?: string;
  subtitle?: string;
  summary?: React.ReactNode;
  total?: number;
  showing?: number;
  onRefresh?: () => void;
  filtersSummary?: string;
  refreshLabel?: string;
  children?: React.ReactNode;
};

export function Toolbar({
  title = "Framegrab Tagger",
  subtitle = "Browse frames, audit predictions, and curate overrides.",
  summary,
  total,
  showing,
  filtersSummary,
  onRefresh,
  refreshLabel = "Refresh feed",
  children,
}: Props) {
  const fallbackSummary =
    total !== undefined ? (
      <div style={{ color: "var(--muted)", marginTop: 4 }}>
        {filtersSummary ? <span style={{ marginRight: 12 }}>{filtersSummary}</span> : null}
        <strong>{showing ?? total}</strong> shown / <strong>{total}</strong> total
      </div>
    ) : null;

  return (
    <header className="panel toolbar">
      <div className="toolbar__title">
        <h1>{title}</h1>
        <span>{subtitle}</span>
        {summary ?? fallbackSummary}
      </div>
      <div className="toolbar__actions">
        {children}
        {onRefresh ? (
          <button className="button button--primary" onClick={onRefresh}>
            {refreshLabel}
          </button>
        ) : null}
      </div>
    </header>
  );
}
