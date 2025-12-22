import { useMemo, useState } from "react";
import useSWR from "swr";

type StorageItem = {
  key: string;
  size?: number;
  last_modified?: string;
  storage_uri: string;
  signed_url?: string | null;
};

type StorageResponse = {
  bucket: string;
  items: StorageItem[];
  prefix?: string | null;
  truncated: boolean;
  next_cursor?: string | null;
};

type Props = {
  authToken: string;
  onSelect: (storageUri: string, filePath: string) => void;
  message?: string | null;
};

const fetcher = async ([url, token]: [string, string]) => {
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<StorageResponse>;
};

export function StorageExplorer({ authToken, onSelect, message }: Props) {
  const [prefix, setPrefix] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);

  const url = useMemo(() => {
    const params = new URLSearchParams();
    if (prefix) params.set("prefix", prefix);
    if (cursor) params.set("cursor", cursor);
    return `/api/frames/storage${params.size ? `?${params.toString()}` : ""}`;
  }, [cursor, prefix]);

  const { data, error, isLoading, mutate } = useSWR(
    authToken ? [url, authToken] : null,
    fetcher,
    { revalidateOnFocus: false },
  );

  const handleReset = () => {
    setCursor(null);
    void mutate();
  };

  const handleSelect = (item: StorageItem) => {
    onSelect(item.storage_uri, item.key);
  };

  return (
    <div className="panel" style={{ marginBottom: "1rem", padding: "1rem 1.25rem" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <div>
          <h3 style={{ margin: 0 }}>Storage explorer</h3>
          <p style={{ margin: "0.15rem 0", color: "var(--muted)" }}>
            Browse objects from the frames bucket and load them into the editor.
          </p>
        </div>
        <button className="button" onClick={() => void mutate()} disabled={!authToken}>
          Refresh storage
        </button>
      </div>

      {!authToken ? (
        <p style={{ color: "var(--danger)" }}>
          Provide a moderator/admin token to browse the bucket.
        </p>
      ) : null}

      <div style={{ display: "flex", gap: 8, margin: "0.75rem 0" }}>
        <input
          className="input"
          placeholder="Prefix (e.g. frames/2024/)"
          value={prefix}
          onChange={(event) => setPrefix(event.target.value)}
          style={{ flex: 1 }}
        />
        <button className="button" onClick={handleReset} disabled={isLoading}>
          Apply
        </button>
      </div>

      {message ? <p style={{ color: "var(--success)" }}>{message}</p> : null}
      {error ? <p style={{ color: "var(--danger)" }}>{(error as Error).message}</p> : null}

      {isLoading ? <p className="muted">Loading objects...</p> : null}
      {data?.items?.length ? (
        <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
          {data.items.map((item) => (
            <article key={item.key} className="card" style={{ cursor: "default" }}>
              <div className="card__image" style={{ height: 140 }}>
                {item.signed_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={item.signed_url} alt={item.key} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                ) : (
                  <div className="empty-state" style={{ height: "100%", justifyContent: "center" }}>
                    No preview
                  </div>
                )}
              </div>
              <div className="card__meta">
                <h3 style={{ wordBreak: "break-all" }}>{item.key}</h3>
                <span>{item.size ? `${(item.size / 1024).toFixed(1)} KB` : "Unknown size"}</span>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
                  <small className="muted">{item.last_modified ? new Date(item.last_modified).toLocaleString() : "—"}</small>
                  <button className="button button--primary" onClick={() => handleSelect(item)}>
                    Load
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="muted">No objects found for this prefix.</p>
      )}

      {data?.truncated && data.next_cursor ? (
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8, gap: 8 }}>
          <button className="button" onClick={() => setCursor(data.next_cursor ?? null)}>
            Load more
          </button>
        </div>
      ) : null}
    </div>
  );
}
