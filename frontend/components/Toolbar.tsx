type Props = {
  total: number;
  showing?: number;
  onRefresh?: () => void;
  filtersSummary?: string;
  children?: React.ReactNode;
};

export function Toolbar({ total, showing, filtersSummary, onRefresh, children }: Props) {
  return (
    <header className="panel toolbar">
      <div className="toolbar__title">
        <h1>Framegrab Tagger</h1>
        <span>Browse frames, audit predictions, and curate overrides.</span>
        <div style={{ color: "var(--muted)", marginTop: 4 }}>
          {filtersSummary ? <span style={{ marginRight: 12 }}>{filtersSummary}</span> : null}
          <strong>{showing ?? total}</strong> shown / <strong>{total}</strong> total
        </div>
      </div>
      <div className="toolbar__actions">
        {children}
        <button className="button button--primary" onClick={onRefresh}>
          Refresh feed
        </button>
      </div>
    </header>
  );
}
