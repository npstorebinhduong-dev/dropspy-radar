"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

type Source = {
  id: string;
  name: string;
  kind: string;
  corpus_types: string[];
  countries: string[];
  supported_filters: string[];
  approval_status: string;
  rights_reference: string;
  live_enabled: boolean;
  import_enabled: boolean;
  media_storage_allowed: boolean;
  retention_days: number | null;
  state: string;
};
type Job = {
  run_id: string | null;
  id: string;
  filename: string;
  source_id: string;
  dataset_id: string;
  data_label: "REAL" | "DEMO";
  corpus: string;
  status: string;
  total_rows: number;
  valid_rows: number;
  error_count: number;
  processed: number;
  progress: number;
  completeness: string;
  created_at: string;
  mapping: Record<string, string>;
  headers?: string[];
  fields?: string[];
  sample?: { row_number: number; record: Record<string, unknown> }[];
  errors: { row: number | null; field: string; message: string }[];
};
type Tab = "sources" | "import" | "history";
async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, options);
  const body = await response.json();
  if (!response.ok)
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail || "Request failed"),
    );
  return body;
}

export default function DataWorkspace({
  initialTab = "sources",
  onSearch,
}: {
  initialTab?: Tab;
  onSearch?: (mode: "demo" | "real") => void;
}) {
  const [tab, setTab] = useState<Tab>(initialTab);
  const [sources, setSources] = useState<Source[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [label, setLabel] = useState<"REAL" | "DEMO">("REAL");
  const [source, setSource] = useState("authorized-file");
  const [dataset, setDataset] = useState("my-dataset");
  const [corpus, setCorpus] = useState("paid_ad");
  const [rights, setRights] = useState("");
  const [attested, setAttested] = useState(false);
  const [completeness, setCompleteness] = useState("partial");
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<Job | null>(null);
  const [inspected, setInspected] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [historyError, setHistoryError] = useState("");
  const selectedSource = sources.find((s) => s.id === source);
  const importActive = jobs.some((j) =>
    ["queued", "running"].includes(j.status),
  );
  const refresh = useCallback(async () => {
    try {
      const [registry, history] = await Promise.all([
        api<{ items: Source[] }>("/sources"),
        api<{ items: Job[]; total: number }>(`/imports?page=${page}`),
      ]);
      setSources(registry.items);
      setJobs(history.items);
      setTotal(history.total);
      setHistoryError("");
    } catch (e) {
      setHistoryError(
        e instanceof Error ? e.message : "Unable to load sources/imports",
      );
    } finally {
      setLoading(false);
    }
  }, [page]);
  useEffect(() => {
    const timer = setTimeout(() => void refresh(), 0);
    return () => clearTimeout(timer);
  }, [refresh]);
  useEffect(() => {
    if (!importActive) return;
    const timer = setInterval(() => void refresh(), 1000);
    return () => clearInterval(timer);
  }, [importActive, refresh]);
  function invalidate() {
    setPreview(null);
    setNotice("");
  }
  async function makePreview() {
    if (!file) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const data = new FormData();
      data.append("file", file);
      data.append(
        "options",
        JSON.stringify({
          source_id: source,
          dataset_id: dataset,
          data_label: label,
          corpus,
          rights_reference: rights,
          permission_attested: attested,
          completeness,
          mapping,
        }),
      );
      const result = await api<Job>("/imports/preview", {
        method: "POST",
        body: data,
      });
      setPreview(result);
      setMapping(result.mapping);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Preview failed");
    } finally {
      setBusy(false);
    }
  }
  async function start(id: string, retry = false) {
    setBusy(true);
    setError("");
    try {
      const result = await api<Job>(
        `/imports/${id}/${retry ? "retry" : "start"}`,
        { method: "POST" },
      );
      setPreview(null);
      setNotice(
        `Import ${result.status}. Progress is shown in Import History.`,
      );
      setTab("history");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import could not start");
    } finally {
      setBusy(false);
    }
  }
  async function inspect(id: string) {
    try {
      setInspected(await api<Job>(`/imports/${id}`));
      setError("");
    } catch (e) {
      setError(String(e));
    }
  }
  return (
    <section className="data-workspace">
      <div className="data-heading">
        <div>
          <h2>Data workspace</h2>
          <p>
            Upload data you may use. Review mappings and preview before
            importing. No external URLs are fetched.
          </p>
        </div>
        <div className="data-route-links">
          <Link href="/data-sources">Sources page</Link>
          <Link href="/import-history">History page</Link>
        </div>
      </div>
      <nav className="data-tabs" aria-label="Data workspace sections">
        {(
          [
            ["sources", "Data Sources"],
            ["import", "Import Data"],
            ["history", "Import History"],
          ] as const
        ).map(([id, title]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={tab === id ? "active" : ""}
          >
            {title}
          </button>
        ))}
      </nav>
      {error && (
        <p role="alert" className="error-panel">
          {error}
        </p>
      )}
      {historyError && (
        <p role="alert" className="error-panel">
          {historyError}
          <button onClick={() => void refresh()}>Retry</button>
        </p>
      )}
      {notice && (
        <p role="status" className="import-notice">
          {notice}
        </p>
      )}
      {loading ? (
        <p role="status">Loading data workspace…</p>
      ) : tab === "sources" ? (
        <div className="source-grid">
          {sources.map((s) => (
            <article className="source-card" key={s.id}>
              <h3>{s.name}</h3>
              <span className={`data-label label-${s.state}`}>{s.state}</span>
              <dl>
                <dt>Source ID / type</dt>
                <dd>
                  {s.id} · {s.kind}
                </dd>
                <dt>Corpus</dt>
                <dd>{s.corpus_types.join(", ")}</dd>
                <dt>Approval / collection</dt>
                <dd>
                  {s.approval_status} · Live{" "}
                  {s.live_enabled ? "enabled" : "off"} · Import{" "}
                  {s.import_enabled ? "enabled" : "off"}
                </dd>
                <dt>Markets</dt>
                <dd>
                  {s.countries.length
                    ? s.countries.join(", ")
                    : "Not configured"}
                </dd>
                <dt>Supported filters</dt>
                <dd>{s.supported_filters.join(", ") || "None configured"}</dd>
                <dt>Media / raw retention</dt>
                <dd>
                  {s.media_storage_allowed
                    ? "Storage allowed"
                    : "No media storage"}{" "}
                  ·{" "}
                  {s.retention_days
                    ? `${s.retention_days} days`
                    : "Unspecified; source disabled"}
                </dd>
                <dt>Rights</dt>
                <dd>{s.rights_reference}</dd>
              </dl>
              {s.import_enabled && (
                <button
                  className="secondary"
                  onClick={() => {
                    setSource(s.id);
                    setLabel(s.id === "demo" ? "DEMO" : "REAL");
                    setCorpus(s.id === "demo" ? "demo" : "paid_ad");
                    invalidate();
                    setTab("import");
                  }}
                >
                  Import from this source
                </button>
              )}
            </article>
          ))}
        </div>
      ) : tab === "import" ? (
        <div className="import-form">
          <div className="import-fields">
            <label>
              Data label
              <select
                aria-label="Import data label"
                value={label}
                onChange={(e) => {
                  const next = e.target.value as "REAL" | "DEMO";
                  setLabel(next);
                  setSource(next === "DEMO" ? "demo" : "authorized-file");
                  setCorpus(next === "DEMO" ? "demo" : "paid_ad");
                  invalidate();
                }}
              >
                <option>REAL</option>
                <option>DEMO</option>
              </select>
            </label>
            <label>
              Source
              <select
                aria-label="Import source"
                value={source}
                onChange={(e) => {
                  setSource(e.target.value);
                  invalidate();
                }}
              >
                {sources
                  .filter(
                    (s) =>
                      s.import_enabled &&
                      (label === "DEMO" ? s.id === "demo" : s.id !== "demo"),
                  )
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Dataset identity
              <input
                aria-label="Dataset identity"
                value={dataset}
                onChange={(e) => {
                  setDataset(e.target.value);
                  invalidate();
                }}
                placeholder="stable-source-dataset"
              />
            </label>
            <label>
              Corpus
              <select
                value={corpus}
                onChange={(e) => {
                  setCorpus(e.target.value);
                  invalidate();
                }}
              >
                {selectedSource?.corpus_types.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
            <label>
              Collection completeness
              <select
                value={completeness}
                onChange={(e) => {
                  setCompleteness(e.target.value);
                  invalidate();
                }}
              >
                <option value="partial">Partial / unknown</option>
                <option value="capped">Capped sample</option>
                <option value="complete">Complete for declared scope</option>
              </select>
            </label>
          </div>
          <p className="muted">
            Use the same dataset identity to update the same source&apos;s ads.
            Absence from a file never marks an ad inactive. Test fixtures must
            use DEMO.
          </p>
          <label className="file-upload">
            CSV or JSON · UTF-8 · max 2 MiB / 2,000 rows
            <input
              aria-label="Advertising data file"
              type="file"
              accept=".json,.csv,application/json,text/csv"
              onChange={(e) => {
                setFile(e.target.files?.[0] || null);
                setMapping({});
                invalidate();
              }}
            />
          </label>
          {label === "REAL" && (
            <>
              <label className="rights-field">
                Rights reference
                <input
                  aria-label="Rights reference"
                  value={rights}
                  onChange={(e) => {
                    setRights(e.target.value);
                    invalidate();
                  }}
                  placeholder="Dataset license or permission reference"
                />
              </label>
              <label className="attestation">
                <input
                  type="checkbox"
                  checked={attested}
                  onChange={(e) => {
                    setAttested(e.target.checked);
                    invalidate();
                  }}
                />
                I have permission to import and use this dataset. This is my
                declaration, not platform verification.
              </label>
            </>
          )}
          <button
            className="primary"
            disabled={
              busy ||
              !file ||
              (label === "REAL" && (!attested || rights.trim().length < 10))
            }
            onClick={() => void makePreview()}
          >
            {busy ? "Validating…" : "Preview file"}
          </button>
          {preview && (
            <section className="preview-panel">
              <h3>
                Preview: {preview.valid_rows} valid / {preview.total_rows} rows
                · {preview.error_count} errors · {preview.data_label}
              </h3>
              <p>
                Nothing is ingested until you select Import valid rows. Preview
                can be remapped; new mappings require another preview.
              </p>
              <div className="mapping-grid">
                {preview.fields?.map((field) => (
                  <label key={field}>
                    {field}
                    <select
                      aria-label={`Map ${field}`}
                      value={mapping[field] || ""}
                      onChange={(e) => {
                        setMapping({ ...mapping, [field]: e.target.value });
                        setPreview({ ...preview, status: "mapping_changed" });
                      }}
                    >
                      <option value="">Not mapped</option>
                      {preview.headers?.map((h) => (
                        <option key={h}>{h}</option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
              <button
                className="secondary"
                disabled={busy}
                onClick={() => void makePreview()}
              >
                Revalidate mapping
              </button>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>File row</th>
                      <th>Normalized data</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.sample?.map((row) => (
                      <tr key={row.row_number}>
                        <td>{row.row_number}</td>
                        <td>
                          <pre>{JSON.stringify(row.record, null, 2)}</pre>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {preview.errors.map((e, i) => (
                <p key={i} className="row-error">
                  Row {e.row}: {e.field} — {e.message}
                </p>
              ))}
              {preview.error_count > 100 && (
                <p>Showing first 100 row errors.</p>
              )}
              <button
                className="primary"
                disabled={
                  busy ||
                  preview.valid_rows === 0 ||
                  preview.status !== "preview"
                }
                onClick={() => void start(preview.id)}
              >
                Import valid rows
              </button>
              {["completed", "completed_with_errors"].includes(
                preview.status,
              ) && (
                <p>
                  This exact import already completed. No duplicate import is
                  needed.
                </p>
              )}
            </section>
          )}
        </div>
      ) : (
        <div className="import-history">
          <div className="history-toolbar">
            <h3>Import History ({total})</h3>
            <button className="secondary" onClick={() => void refresh()}>
              Refresh history
            </button>
          </div>
          {jobs.length === 0 ? (
            <div className="empty-state">
              <h3>No imports yet</h3>
              <p>Create a preview to begin.</p>
              <button className="primary" onClick={() => setTab("import")}>
                Import a file
              </button>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>File / source</th>
                    <th>Label / completeness</th>
                    <th>Progress</th>
                    <th>Status / errors</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((j) => (
                    <tr key={j.id}>
                      <td>
                        {j.filename}
                        <small>
                          {j.dataset_id} · {j.source_id}
                        </small>
                      </td>
                      <td>
                        <span className="data-label">{j.data_label}</span>{" "}
                        {j.completeness}
                      </td>
                      <td>
                        <progress max={100} value={j.progress} />
                        <small>
                          {j.processed}/{j.total_rows}
                        </small>
                      </td>
                      <td>
                        {j.status}
                        <small>{j.error_count} validation errors</small>
                      </td>
                      <td>
                        <button
                          className="text-button"
                          onClick={() => void inspect(j.id)}
                        >
                          Details / errors
                        </button>
                        {j.status === "failed" && (
                          <button
                            className="secondary"
                            disabled={busy}
                            onClick={() => void start(j.id, true)}
                          >
                            Retry remaining rows
                          </button>
                        )}
                        {["completed", "completed_with_errors"].includes(
                          j.status,
                        ) &&
                          (onSearch ? (
                            <button
                              className="secondary"
                              onClick={() =>
                                onSearch(
                                  j.data_label === "DEMO" ? "demo" : "real",
                                )
                              }
                            >
                              Search imported ads
                            </button>
                          ) : (
                            <Link
                              className="secondary"
                              href={`/?data_mode=${j.data_label === "DEMO" ? "demo" : "real"}`}
                            >
                              Search imported ads
                            </Link>
                          ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="pagination">
            <button disabled={page === 1} onClick={() => setPage(page - 1)}>
              Previous imports
            </button>
            <span>Page {page}</span>
            <button
              disabled={page * 20 >= total}
              onClick={() => setPage(page + 1)}
            >
              Next imports
            </button>
          </div>
          {inspected && (
            <section className="preview-panel">
              <button className="secondary" onClick={() => setInspected(null)}>
                Close import details
              </button>
              <h3>
                {inspected.filename} · {inspected.status}
              </h3>
              <a
                className="secondary"
                href={`/api/v1/imports/${inspected.id}/errors`}
                download
              >
                Download full error report
              </a>
              <p>
                Run {inspected.run_id || "not started"} · dataset{" "}
                {inspected.dataset_id}
              </p>
              {inspected.errors.length ? (
                inspected.errors.map((e, i) => (
                  <p className="row-error" key={i}>
                    Row {e.row ?? "batch"}: {e.field} — {e.message}
                  </p>
                ))
              ) : (
                <p>No validation errors.</p>
              )}
            </section>
          )}
        </div>
      )}
    </section>
  );
}
