import { useEffect, useState } from "react";

type RuntimeSettings = {
  storageEndpointUrl: string;
  storageAccessKey: string;
  storageSecretKey: string;
  storageFramesBucket: string;
  tmdbApiKey: string;
  omdbApiKey: string;
};

const emptySettings: RuntimeSettings = {
  storageEndpointUrl: "",
  storageAccessKey: "",
  storageSecretKey: "",
  storageFramesBucket: "",
  tmdbApiKey: "",
  omdbApiKey: "",
};

export function SettingsPanel() {
  const [adminToken, setAdminToken] = useState("");
  const [settings, setSettings] = useState<RuntimeSettings>(emptySettings);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem("movietagAdminToken");
    if (stored) {
      setAdminToken(stored);
    }
  }, []);

  useEffect(() => {
    const fetchSettings = async () => {
      if (!adminToken) {
        setSettings(emptySettings);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const response = await fetch("/api/settings", {
          headers: { Authorization: `Bearer ${adminToken}` },
        });
        if (!response.ok) {
          throw new Error(`Unable to load settings (${response.status})`);
        }
        const data = await response.json();
        setSettings({
          storageEndpointUrl: data.storage_endpoint_url ?? "",
          storageAccessKey: data.storage_access_key ?? "",
          storageSecretKey: data.storage_secret_key ?? "",
          storageFramesBucket: data.storage_frames_bucket ?? "",
          tmdbApiKey: data.tmdb_api_key ?? "",
          omdbApiKey: data.omdb_api_key ?? "",
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load settings.");
      } finally {
        setLoading(false);
      }
    };

    void fetchSettings();
  }, [adminToken]);

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    setError(null);
    try {
      const response = await fetch("/api/settings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${adminToken}`,
        },
        body: JSON.stringify({
          storage_endpoint_url: settings.storageEndpointUrl || null,
          storage_access_key: settings.storageAccessKey || null,
          storage_secret_key: settings.storageSecretKey || null,
          storage_frames_bucket: settings.storageFramesBucket || null,
          tmdb_api_key: settings.tmdbApiKey || null,
          omdb_api_key: settings.omdbApiKey || null,
        }),
      });

      const responseBody = await response.text();
      if (!response.ok) {
        let message = responseBody || "Unable to save settings.";
        try {
          const parsed = JSON.parse(responseBody);
          message = parsed.detail || message;
        } catch {
          // ignore json parse errors and fall back to raw text
        }
        throw new Error(message);
      }

      try {
        const parsed = JSON.parse(responseBody);
        setSettings({
          storageEndpointUrl: parsed.storage_endpoint_url ?? "",
          storageAccessKey: parsed.storage_access_key ?? "",
          storageSecretKey: parsed.storage_secret_key ?? "",
          storageFramesBucket: parsed.storage_frames_bucket ?? "",
          tmdbApiKey: parsed.tmdb_api_key ?? "",
          omdbApiKey: parsed.omdb_api_key ?? "",
        });
      } catch {
        // If parsing fails, keep the optimistic state the user entered.
      }

      setStatus("Settings saved. New values will be used for future uploads and metadata calls.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save settings.");
    } finally {
      setSaving(false);
    }
  };

  const updateToken = (value: string) => {
    setAdminToken(value);
    if (value) {
      window.localStorage.setItem("movietagAdminToken", value);
    } else {
      window.localStorage.removeItem("movietagAdminToken");
    }
  };

  return (
    <div className="sidebar__section" aria-live="polite">
      <h4>Backend configuration</h4>
      <p>Provide the admin token to update storage and metadata provider settings.</p>

      <label className="label" htmlFor="adminToken">
        Admin bearer token
      </label>
      <input
        id="adminToken"
        className="input"
        type="password"
        placeholder="APP_ADMIN_TOKEN value"
        value={adminToken}
        onChange={(event) => updateToken(event.target.value)}
      />
      {!adminToken ? (
        <p style={{ color: "var(--muted)", margin: "0.25rem 0" }}>
          Enter a token to load and save settings.
        </p>
      ) : null}

      <div style={{ display: "grid", gap: "0.5rem", marginTop: "1rem" }}>
        <label className="label" htmlFor="storageEndpoint">
          Storage endpoint URL
        </label>
        <input
          id="storageEndpoint"
          className="input"
          placeholder="https://minio.example.com"
          value={settings.storageEndpointUrl}
          onChange={(event) =>
            setSettings((prev) => ({ ...prev, storageEndpointUrl: event.target.value }))
          }
          disabled={!adminToken || loading}
        />

        <label className="label" htmlFor="storageAccessKey">
          Storage access key
        </label>
        <input
          id="storageAccessKey"
          className="input"
          placeholder="Access key"
          value={settings.storageAccessKey}
          onChange={(event) =>
            setSettings((prev) => ({ ...prev, storageAccessKey: event.target.value }))
          }
          disabled={!adminToken || loading}
        />

        <label className="label" htmlFor="storageSecretKey">
          Storage secret key
        </label>
        <input
          id="storageSecretKey"
          className="input"
          type="password"
          placeholder="Secret key"
          value={settings.storageSecretKey}
          onChange={(event) =>
            setSettings((prev) => ({ ...prev, storageSecretKey: event.target.value }))
          }
          disabled={!adminToken || loading}
        />

        <label className="label" htmlFor="storageBucket">
          Frames bucket
        </label>
        <input
          id="storageBucket"
          className="input"
          placeholder="frames"
          value={settings.storageFramesBucket}
          onChange={(event) =>
            setSettings((prev) => ({ ...prev, storageFramesBucket: event.target.value }))
          }
          disabled={!adminToken || loading}
        />

        <label className="label" htmlFor="tmdbKey">
          TMDb API key
        </label>
        <input
          id="tmdbKey"
          className="input"
          placeholder="TMDb v4 token"
          value={settings.tmdbApiKey}
          onChange={(event) =>
            setSettings((prev) => ({ ...prev, tmdbApiKey: event.target.value }))
          }
          disabled={!adminToken || loading}
        />

        <label className="label" htmlFor="omdbKey">
          OMDb API key
        </label>
        <input
          id="omdbKey"
          className="input"
          placeholder="OMDb API key"
          value={settings.omdbApiKey}
          onChange={(event) =>
            setSettings((prev) => ({ ...prev, omdbApiKey: event.target.value }))
          }
          disabled={!adminToken || loading}
        />
      </div>

      {status ? (
        <p style={{ color: "var(--success)", marginTop: "0.75rem" }}>{status}</p>
      ) : null}
      {error ? (
        <p style={{ color: "var(--danger)", marginTop: "0.75rem" }}>{error}</p>
      ) : null}

      <button
        className="button button--primary"
        style={{ marginTop: "1rem", width: "100%" }}
        onClick={handleSave}
        disabled={!adminToken || saving || loading}
      >
        {saving ? "Saving..." : "Save settings"}
      </button>
    </div>
  );
}
