type Props = {
  total: number;
  onRefresh?: () => void;
  children?: React.ReactNode;
};

export function Toolbar({ total, onRefresh, children }: Props) {
  return (
    <header className="panel toolbar">
      <div className="toolbar__title">
        <h1>Framegrab Tagger</h1>
        <span>Browse frames, audit predictions, and curate overrides.</span>
      </div>
      <div className="toolbar__actions">
        <span className="pill">
          <strong>{total}</strong> frames
        </span>
        {children}
        <button className="button button--primary" onClick={onRefresh}>
          Refresh feed
        </button>
      </div>
    </header>
  );
}
