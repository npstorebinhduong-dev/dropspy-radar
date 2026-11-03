"use client";

import Link from "next/link";
import DataWorkspace from "../components/DataWorkspace";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowDownUp,
  ArrowRight,
  Bookmark,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Compass,
  ExternalLink,
  Layers3,
  LayoutDashboard,
  LoaderCircle,
  Radar,
  Search,
  Settings,
  SlidersHorizontal,
  Sparkles,
  Target,
  TrendingUp,
  X,
} from "lucide-react";

type Metric = {
  metric: string;
  value: number;
  maximum: number;
  source: string;
  evidence: string;
  confidence: string;
};
type Ad = {
  id: number;
  data_label: "REAL" | "DEMO" | "UNKNOWN";
  source_name: string;
  registry_source_id: string | null;
  corpus: string;
  title: string;
  advertiser: string;
  platform: string;
  country: string;
  landing_domain: string;
  landing_url: string;
  source_url: string;
  first_seen: string;
  last_seen: string;
  status: string;
  saved: boolean;
  is_demo: boolean;
  creatives: { text: string }[];
  status_evidence: {
    freshness: string;
    age_hours: number;
    observed_at: string;
    currently_running_verified: boolean;
  };
  score: {
    value: number;
    confidence: string;
    components: Metric[];
    disclaimer: string;
  };
};
type Analysis = {
  version: string;
  method: string;
  status_evidence: { reason: string; freshness: string; observed_at: string };
  signals: {
    category: string;
    label: string;
    excerpt: string;
    creative_index: number;
    confidence: string;
  }[];
  observations: { count: number; span_days: number };
  creative_variants: { count: number; definition: string };
  advertiser: { related_ads: number; identity_method: string };
  source: {
    kind: string;
    source_url: string;
    rights_reference?: string;
    details?: {
      placements?: string[];
      media_urls?: string[];
      coverage?: string;
    };
  };
  limitations: string[];
};
type Overview = {
  total_ads: number;
  advertisers: number;
  active_ads: number;
  saved_ads: number;
  mode: string;
};
type Competitor = {
  advertiser: string;
  ad_count: number;
  first_seen: string;
  last_seen: string;
  source: string;
};
const navigation = [
  { name: "Overview", icon: LayoutDashboard },
  { name: "Meta Ads Search", icon: Search },
  { name: "TikTok Ads Search", icon: Compass },
  { name: "Product Intelligence", icon: Sparkles },
  { name: "Competitor Tracker", icon: Target },
  { name: "Saved Ads", icon: Bookmark },
  { name: "Settings", icon: Settings },
];
const illustrations = [
  "◒",
  "≈",
  "✳",
  "◉",
  "▤",
  "⌁",
  "✺",
  "◍",
  "▰",
  "☁",
  "◡",
  "◐",
];
const date = (value: string) =>
  new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${url}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : detail?.message || `API request failed (${response.status}).`,
    );
  }
  return response.json();
}

export default function Dashboard() {
  const [dataMode, setDataMode] = useState<"demo" | "real">("demo");
  const [sourceFilter, setSourceFilter] = useState("");
  const [evidence, setEvidence] = useState<{
    items: {
      id: number;
      source_id: string;
      raw_data: Record<string, unknown>;
      normalized_data: Record<string, unknown>;
      observed_at: string;
      rights_reference: string;
      run_id: string;
    }[];
    total: number;
    page: number;
  } | null>(null);
  const [view, setView] = useState("Overview");
  const [ads, setAds] = useState<Ad[]>([]);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Ad | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [analysisError, setAnalysisError] = useState("");
  const detailRequest = useRef(0);
  const [collecting, setCollecting] = useState(false);
  const [discoveryMessage, setDiscoveryMessage] = useState("");
  const [recentDays, setRecentDays] = useState("");
  const [minDays, setMinDays] = useState("0");
  const [history, setHistory] = useState<
    { observed_at: string; status: string; source_url: string }[]
  >([]);
  const [filters, setFilters] = useState(false);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [country, setCountry] = useState("US");
  const [platform, setPlatform] = useState("");
  const [status, setStatus] = useState("active");
  const [advertiser, setAdvertiser] = useState("");
  const [domain, setDomain] = useState("");
  const [after, setAfter] = useState("");
  const [before, setBefore] = useState("");
  const [sort, setSort] = useState("newest");
  const load = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError("");
      const params = new URLSearchParams({
        q: query,
        data_mode: dataMode,
        source: sourceFilter,
        country: country === "EU" ? "" : country,
        market: country === "EU" ? "EU" : "",
        platform:
          view === "Meta Ads Search"
            ? ["facebook", "instagram", "reels"].includes(platform)
              ? platform
              : "meta"
            : view === "TikTok Ads Search"
              ? "tiktok"
              : platform,
        status,
        min_observed_days: minDays,
        advertiser,
        domain,
        sort,
        page: String(page),
        page_size: "9",
        saved: String(view === "Saved Ads"),
      });
      if (recentDays) params.set("observed_within_days", recentDays);
      if (after) params.set("detected_after", `${after}T00:00:00`);
      if (before) params.set("detected_before", `${before}T23:59:59.999999`);
      try {
        const [result, stats, rivals] = await Promise.all([
          request<{ items: Ad[]; total: number }>(`/ads?${params}`, { signal }),
          request<Overview>(`/overview?data_mode=${dataMode}`, { signal }),
          request<Competitor[]>(`/competitors?data_mode=${dataMode}`, {
            signal,
          }),
        ]);
        if (signal?.aborted) return;
        setAds(result.items);
        setTotal(result.total);
        setOverview(stats);
        setCompetitors(rivals);
      } catch (e) {
        if (!signal?.aborted)
          setError(e instanceof Error ? e.message : "Unable to load ads");
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [
      query,
      country,
      platform,
      status,
      advertiser,
      domain,
      sort,
      page,
      view,
      after,
      before,
      recentDays,
      minDays,
      dataMode,
      sourceFilter,
    ],
  );
  useEffect(() => {
    const timer = setTimeout(() => {
      if (
        new URLSearchParams(window.location.search).get("data_mode") === "real"
      ) {
        setDataMode("real");
        setStatus("");
        setCountry("");
      }
    }, 0);
    return () => clearTimeout(timer);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => void load(controller.signal), 200);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [load]);
  async function save(ad: Ad) {
    try {
      await request(
        `/ads/${ad.id}/saved?saved=${!ad.saved}&data_mode=${dataMode}`,
        {
          method: "PUT",
        },
      );
      if (selected?.id === ad.id) setSelected({ ...ad, saved: !ad.saved });
      await load();
    } catch (e) {
      setError(String(e));
    }
  }
  async function inspect(ad: Ad) {
    const requestId = ++detailRequest.current;
    setSelected(ad);
    setHistory([]);
    setAnalysis(null);
    setEvidence(null);
    setAnalysisError("");
    try {
      const [observations, details, raw] = await Promise.all([
        request<{ observed_at: string; status: string; source_url: string }[]>(
          `/ads/${ad.id}/observations?data_mode=${dataMode}`,
        ),
        request<Analysis>(`/ads/${ad.id}/analysis?data_mode=${dataMode}`),
        request<{
          items: {
            id: number;
            source_id: string;
            raw_data: Record<string, unknown>;
            normalized_data: Record<string, unknown>;
            observed_at: string;
            rights_reference: string;
            run_id: string;
          }[];
          total: number;
          page: number;
        }>(`/ads/${ad.id}/evidence?data_mode=${dataMode}`),
      ]);
      if (requestId === detailRequest.current) {
        setHistory(observations);
        setAnalysis(details);
        setEvidence(raw);
      }
    } catch (e) {
      if (requestId === detailRequest.current) setAnalysisError(String(e));
    }
  }
  function closeDetail() {
    detailRequest.current++;
    setSelected(null);
  }
  async function discoverMeta() {
    setCollecting(true);
    setDiscoveryMessage("");
    try {
      const result = await request<{
        records_processed: number;
        skipped: number;
        coverage: string;
      }>("/discovery/meta", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ q: query.trim(), country: country || "US" }),
      });
      setDiscoveryMessage(
        `Read ${result.records_processed} ads; ${result.skipped} incomplete/non-active rows skipped. ${result.coverage}.`,
      );
      setPage(1);
      await load();
    } catch (e) {
      setDiscoveryMessage(
        e instanceof Error ? e.message : "Public search unavailable",
      );
    } finally {
      setCollecting(false);
    }
  }
  const metaLibraryUrl =
    "https://www.facebook.com/ads/library/?" +
    new URLSearchParams({
      active_status: "active",
      ad_type: "all",
      country: country || "US",
      q: query,
      search_type: "keyword_unordered",
      media_type: "all",
    });
  function changeView(value: string) {
    setView(value);
    setPage(1);
    closeDetail();
    setDiscoveryMessage("");
  }
  const demo = dataMode === "demo";
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" href="/">
          <span className="brand-mark">
            <Radar size={25} />
          </span>
          <span>
            DROPSpy<span className="brand-sub">RADAR</span>
          </span>
        </Link>
        <div className="workspace">
          <span className="workspace-icon">D</span>
          <div>
            Discovery workspace<small>Personal workspace</small>
          </div>
          <span className="version">v0.2</span>
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav>
          {navigation.map(({ name, icon: Icon }) => (
            <button
              key={name}
              className={`nav-item ${view === name ? "selected" : ""}`}
              onClick={() => changeView(name)}
            >
              <Icon size={18} />
              {name}
              {name === "Saved Ads" && (
                <span className="nav-count">{overview?.saved_ads ?? 0}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <div className="flex items-center gap-2">
            <Activity size={17} />
            <strong>Signals, with context.</strong>
          </div>
          <p>
            Research the creative.
            <br />
            Understand the opportunity.
          </p>
          <span>
            Transparent by design <ArrowRight size={13} />
          </span>
        </div>
        <div className="sidebar-bottom">
          <CircleHelp size={17} />
          <span>Research responsibly</span>
          <span className="avatar">DS</span>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={14} /> <strong>{view}</strong>
          </div>
          <div className="top-actions">
            <span className="status-dot" />{" "}
            {overview ? `${demo ? "Demo" : "Live"} workspace` : "Connecting"}
            <span className="divider" />
            <span className="avatar light">DS</span>
          </div>
        </header>
        <main>
          <div className="demo-banner">
            <span>
              <Sparkles size={16} />
              <strong>
                {demo
                  ? "You’re exploring the demo workspace"
                  : "Research workspace"}
              </strong>
              <span className="banner-copy">
                {demo
                  ? "All ads and signals in this partition are synthetic. Switch to REAL to search imports."
                  : "Imported observations. REAL indicates operator-attested provenance; UNKNOWN means provenance is incomplete."}
              </span>
            </span>
            <span className="demo-tag">
              {demo ? "DEMO DATA" : "NO LIVE COLLECTOR"}
            </span>
          </div>
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                YOUR NEXT PRODUCT STARTS WITH A SIGNAL
              </div>
              <h1>
                {view === "Overview"
                  ? "Discover what’s gaining traction."
                  : view}
              </h1>
              <p>
                {view === "Overview"
                  ? "Explore ads, spot patterns, and turn early signals into your next big idea."
                  : "Explore transparent ad observations. Every signal includes its source and confidence."}
              </p>
            </div>
            <button
              className="secondary"
              onClick={() => changeView("Saved Ads")}
            >
              <Bookmark size={16} /> Your collection <ArrowRight size={16} />
            </button>
          </div>
          {view === "Settings" ? (
            <DataWorkspace
              onSearch={(mode) => {
                setDataMode(mode);
                setStatus("");
                setCountry("");
                setSourceFilter("");
                setPlatform("");
                setQuery("");
                setAdvertiser("");
                setDomain("");
                setAfter("");
                setBefore("");
                setRecentDays("");
                setMinDays("0");
                changeView("Overview");
              }}
            />
          ) : (
            <>
              {view === "Overview" && (
                <div className="stats-grid">
                  {[
                    {
                      label: "Ads in your radar",
                      value: overview?.total_ads,
                      icon: Layers3,
                      note: "Across the selected data partition",
                    },
                    {
                      label: "Active observations",
                      value: overview?.active_ads,
                      icon: Activity,
                      note: "Source-reported status at observation",
                    },
                    {
                      label: "Advertisers discovered",
                      value: overview?.advertisers,
                      icon: Target,
                      note: "Unique names in this dataset",
                    },
                    {
                      label: "Saved to collection",
                      value: overview?.saved_ads,
                      icon: Bookmark,
                      note: "Your research shortlist",
                    },
                  ].map(({ label, value, icon: Icon, note }) => (
                    <div className="stat-card" key={label}>
                      <div className="stat-top">
                        {label}
                        <Icon size={18} />
                      </div>
                      <strong>{value ?? "—"}</strong>
                      <small>
                        <span className="tiny-dot" />
                        {note}
                      </small>
                    </div>
                  ))}
                </div>
              )}
              {view === "Competitor Tracker" ? (
                <section className="settings-panel">
                  <h2>Advertiser observations</h2>
                  <p>
                    Dataset summary; scheduled competitor monitoring is planned.
                  </p>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Advertiser</th>
                          <th>Ads</th>
                          <th>First seen</th>
                          <th>Last seen</th>
                          <th>Source</th>
                        </tr>
                      </thead>
                      <tbody>
                        {competitors.map((c) => (
                          <tr key={c.advertiser}>
                            <td>
                              <button
                                className="text-button"
                                onClick={() => {
                                  setAdvertiser(c.advertiser);
                                  changeView("Meta Ads Search");
                                }}
                              >
                                {c.advertiser}
                              </button>
                            </td>
                            <td>{c.ad_count}</td>
                            <td>{date(c.first_seen)}</td>
                            <td>{date(c.last_seen)}</td>
                            <td>{c.source}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              ) : (
                <>
                  <section className="explore-heading">
                    <div>
                      <h2>
                        {view === "Product Intelligence"
                          ? "Product signals"
                          : view === "Saved Ads"
                            ? "Your saved ads"
                            : "Explore your radar"}
                        <span className="count-pill">{total} ads</span>
                      </h2>
                      <p>
                        {view === "Product Intelligence"
                          ? "Open an ad for score weights, evidence and confidence. Score is a research heuristic."
                          : "A closer look at the creatives and products worth researching."}
                      </p>
                    </div>
                    <span className="market-label">
                      ◎ US first. Global next.
                    </span>
                  </section>
                  <section className="search-panel">
                    <div className="search-row">
                      <label className="search-input">
                        <Search size={19} />
                        <input
                          aria-label="Search ads"
                          placeholder="Search creative text, advertiser, product, or domain…"
                          value={query}
                          onChange={(e) => {
                            setQuery(e.target.value);
                            setPage(1);
                          }}
                        />
                        <span>⌘ K</span>
                      </label>
                      <select
                        aria-label="Country"
                        value={country}
                        onChange={(e) => {
                          setCountry(e.target.value);
                          setPage(1);
                        }}
                      >
                        <option value="US">🇺🇸 United States</option>
                        <option value="">All countries</option>
                        <option value="EU">European Union (27)</option>
                        <option value="DE">🇩🇪 Germany</option>
                      </select>
                      <button
                        className={`secondary ${filters ? "pressed" : ""}`}
                        onClick={() => setFilters(!filters)}
                        aria-expanded={filters}
                      >
                        <SlidersHorizontal size={16} /> Filters
                      </button>
                    </div>
                    <div className="research-toolbar">
                      <label>
                        Dataset{" "}
                        <select
                          aria-label="Search data partition"
                          value={dataMode}
                          onChange={(e) => {
                            setDataMode(e.target.value as "demo" | "real");
                            setPage(1);
                            closeDetail();
                          }}
                        >
                          <option value="demo">DEMO</option>
                          <option value="real">REAL / UNKNOWN</option>
                        </select>
                      </label>
                      <label>
                        Source{" "}
                        <select
                          aria-label="Search data source"
                          value={sourceFilter}
                          onChange={(e) => {
                            setSourceFilter(e.target.value);
                            setPage(1);
                          }}
                        >
                          <option value="">All sources in partition</option>
                          <option value="demo">Demo Data</option>
                          <option value="authorized-file">
                            Authorized File Import
                          </option>
                          <option value="meta-ad-library">
                            Meta Ads Library
                          </option>
                          <option value="tiktok-ad-library">
                            TikTok Ad Library
                          </option>
                          <option value="tiktok-creative-center">
                            TikTok Creative Center
                          </option>
                          <option value="licensed-provider">
                            Licensed Data Provider
                          </option>
                          <option value="legacy-unknown">Legacy unknown</option>
                        </select>
                      </label>
                      <label>
                        Reported status{" "}
                        <select
                          aria-label="Reported ad status"
                          value={status}
                          onChange={(e) => {
                            setStatus(e.target.value);
                            setPage(1);
                          }}
                        >
                          <option value="active">Active</option>
                          <option value="">All statuses</option>
                          <option value="inactive">Inactive</option>
                          <option value="unknown">Unknown</option>
                        </select>
                      </label>
                      <label>
                        Last observed{" "}
                        <select
                          aria-label="Observation freshness"
                          value={recentDays}
                          onChange={(e) => {
                            setRecentDays(e.target.value);
                            setPage(1);
                          }}
                        >
                          <option value="">Any time</option>
                          <option value="3">Within 3 days</option>
                          <option value="7">Within 7 days</option>
                          <option value="30">Within 30 days</option>
                        </select>
                      </label>
                      <label>
                        Observation span{" "}
                        <select
                          aria-label="Minimum observation span"
                          value={minDays}
                          onChange={(e) => {
                            setMinDays(e.target.value);
                            setPage(1);
                          }}
                        >
                          <option value="0">Any span</option>
                          <option value="7">7+ days</option>
                          <option value="14">14+ days</option>
                          <option value="30">30+ days</option>
                        </select>
                      </label>
                    </div>
                    {(view === "Meta Ads Search" || view === "Overview") && (
                      <div className="public-search-panel">
                        <div>
                          <strong>Find active ads in Meta Ad Library</strong>
                          <p>
                            Search stored observations above, or read the public
                            search page. Access gates stop collection. Active
                            status is reported at observation time.
                          </p>
                        </div>
                        <a
                          className="secondary"
                          href={metaLibraryUrl}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Open public library <ExternalLink size={14} />
                        </a>
                        <button
                          className="primary"
                          disabled={
                            collecting || query.trim().length < 2 || demo
                          }
                          onClick={() => void discoverMeta()}
                        >
                          {collecting
                            ? "Reading public page…"
                            : "Read public results"}
                        </button>
                        {demo && (
                          <small>
                            Live collection is off in DEMO. Use the
                            public-library link to research real ads; live mode
                            requires operator configuration.
                          </small>
                        )}
                        {discoveryMessage && (
                          <p role="status">{discoveryMessage}</p>
                        )}
                      </div>
                    )}
                    {filters && (
                      <div className="advanced-filters">
                        <label>
                          Advertiser
                          <input
                            value={advertiser}
                            onChange={(e) => {
                              setAdvertiser(e.target.value);
                              setPage(1);
                            }}
                            placeholder="Advertiser name"
                          />
                        </label>
                        <label>
                          Landing domain
                          <input
                            value={domain}
                            onChange={(e) => {
                              setDomain(e.target.value);
                              setPage(1);
                            }}
                            placeholder="brand.example"
                          />
                        </label>
                        <label>
                          Status
                          <select
                            value={status}
                            onChange={(e) => {
                              setStatus(e.target.value);
                              setPage(1);
                            }}
                          >
                            <option value="">All statuses</option>
                            <option>active</option>
                            <option>inactive</option>
                            <option>unknown</option>
                          </select>
                        </label>
                        <label>
                          Detected after
                          <input
                            type="date"
                            value={after}
                            onChange={(e) => {
                              setAfter(e.target.value);
                              setPage(1);
                            }}
                          />
                        </label>
                        <label>
                          Detected before
                          <input
                            type="date"
                            value={before}
                            onChange={(e) => {
                              setBefore(e.target.value);
                              setPage(1);
                            }}
                          />
                        </label>
                      </div>
                    )}
                    <div className="filter-bottom">
                      <div className="platform-tabs">
                        {[
                          { label: "All platforms", value: "" },
                          { label: "Facebook", value: "facebook" },
                          { label: "Instagram", value: "instagram" },
                          { label: "Reels", value: "reels" },
                          { label: "TikTok", value: "tiktok" },
                        ]
                          .filter((p) =>
                            view === "Meta Ads Search"
                              ? p.value !== "tiktok"
                              : view === "TikTok Ads Search"
                                ? p.value === "tiktok"
                                : true,
                          )
                          .map((p) => (
                            <button
                              key={p.value}
                              className={
                                platform === p.value ||
                                view === "TikTok Ads Search"
                                  ? "active"
                                  : ""
                              }
                              onClick={() => {
                                setPlatform(p.value);
                                setPage(1);
                              }}
                            >
                              {p.label}
                            </button>
                          ))}
                      </div>
                      <label className="sort-label">
                        <ArrowDownUp size={14} />
                        <select
                          aria-label="Sort ads"
                          value={sort}
                          onChange={(e) => {
                            setSort(e.target.value);
                            setPage(1);
                          }}
                        >
                          <option value="newest">Newest discovered</option>
                          <option value="oldest">Oldest discovered</option>
                          <option value="last_seen">Recently observed</option>
                          <option value="longest">
                            Longest observation span
                          </option>
                          <option value="creative_count">
                            Most creative texts
                          </option>
                          <option value="advertiser">Advertiser A–Z</option>
                        </select>
                      </label>
                    </div>
                  </section>
                  {error && (
                    <div role="alert" className="error-panel">
                      {error}
                      <button onClick={() => void load()}>Retry</button>
                    </div>
                  )}
                  {loading ? (
                    <div className="empty-state">
                      <LoaderCircle className="animate-spin" /> Loading
                      observations…
                    </div>
                  ) : ads.length === 0 ? (
                    <div className="empty-state">
                      <Search />
                      <h2>No ads found</h2>
                      <p>
                        Try another filter or save ads to build your collection.
                      </p>
                    </div>
                  ) : (
                    <div className="ad-grid">
                      {ads.map((ad) => (
                        <article className="ad-card" key={ad.id}>
                          <div className="card-header">
                            <span
                              className={`advertiser-avatar art-${ad.id % 6}`}
                            >
                              {ad.advertiser.slice(0, 1)}
                            </span>
                            <div>
                              <strong>{ad.advertiser}</strong>
                              <small>
                                <span className="platform-dot" />
                                {ad.platform} <span>·</span> {ad.country}
                              </small>
                            </div>
                            <button
                              aria-label={`${ad.saved ? "Unsave" : "Save"} ${ad.title}`}
                              className={`save-button ${ad.saved ? "is-saved" : ""}`}
                              onClick={() => void save(ad)}
                            >
                              <Bookmark
                                size={18}
                                fill={ad.saved ? "currentColor" : "none"}
                              />
                            </button>
                          </div>
                          <button
                            className={`creative-art art-${ad.id % 6}`}
                            onClick={() => void inspect(ad)}
                            aria-label={`Inspect ${ad.title}`}
                          >
                            <span className="art-label">
                              {ad.is_demo ? "SAMPLE CREATIVE" : "TEXT CREATIVE"}
                            </span>
                            <span className="art-shape">
                              {
                                illustrations[
                                  (ad.id - 1) % illustrations.length
                                ]
                              }
                            </span>
                            <div className="art-copy">
                              <span>
                                Little things.
                                <br />
                                Everyday better.
                              </span>
                              <small>{ad.title}</small>
                            </div>
                            <span className="creative-badge">
                              {ad.creatives.length} creative
                              {ad.creatives.length === 1 ? "" : "s"}
                            </span>
                          </button>
                          <div className="card-body">
                            <div className="card-status">
                              <span className={`activity-label ${ad.status}`}>
                                <span />
                                {ad.status} · reported
                              </span>
                              <span>
                                {Math.floor(
                                  (new Date(ad.last_seen).getTime() -
                                    new Date(ad.first_seen).getTime()) /
                                    86400000,
                                )}
                                d observed
                              </span>
                            </div>
                            <button
                              className="ad-title"
                              onClick={() => void inspect(ad)}
                            >
                              {ad.title}
                            </button>
                            <p className="freshness-note">
                              {ad.source_name} · {ad.corpus} · {ad.data_label}
                            </p>
                            <p className="freshness-note">
                              Last observed {date(ad.last_seen)} ·{" "}
                              {ad.status_evidence.freshness}
                            </p>
                            <div className="landing-domain">
                              {ad.landing_domain}
                              <ExternalLink size={11} />
                            </div>
                            <div className="card-footer">
                              <button
                                className="score"
                                onClick={() => void inspect(ad)}
                                title="View score methodology"
                              >
                                <TrendingUp size={14} />
                                {ad.score.value}
                                <span>Signal score</span>
                              </button>
                              <span className="data-label">
                                {ad.data_label}
                              </span>
                            </div>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                  <div className="pagination">
                    <span>
                      Showing {total === 0 ? 0 : (page - 1) * 9 + 1}–
                      {Math.min(page * 9, total)} of {total} ads
                    </span>
                    <div>
                      <button
                        aria-label="Previous page"
                        disabled={page === 1}
                        onClick={() => setPage(page - 1)}
                      >
                        <ChevronLeft size={16} />
                      </button>
                      <span>Page {page}</span>
                      <button
                        aria-label="Next page"
                        disabled={page * 9 >= total}
                        onClick={() => setPage(page + 1)}
                      >
                        <ChevronRight size={16} />
                      </button>
                    </div>
                  </div>
                </>
              )}
            </>
          )}
          <footer className="page-footer">
            <span>
              <Radar size={14} /> DROPSpy Radar <span>v0.2</span>
            </span>
            <span>Better research. Informed decisions.</span>
          </footer>
        </main>
      </div>
      {selected && (
        <div className="modal-backdrop" onClick={closeDetail}>
          <section
            className="detail-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Ad intelligence details"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="close-button"
              aria-label="Close details"
              onClick={closeDetail}
            >
              <X />
            </button>
            <span className="demo-tag">
              {selected.data_label} · {selected.source_name}
            </span>
            <h2>{selected.title || "Untitled ad"}</h2>
            <p>
              Corpus: {selected.corpus} · Source:{" "}
              {selected.registry_source_id || "unknown"}
            </p>
            <p>
              {selected.advertiser} · {selected.platform} · {selected.country}
            </p>
            <h3>Ad analysis</h3>
            {analysisError ? (
              <p role="alert">
                {analysisError}
                <button onClick={() => void inspect(selected)}>
                  Retry analysis
                </button>
              </p>
            ) : !analysis ? (
              <p role="status">Loading evidence and creative analysis…</p>
            ) : (
              <div className="analysis-summary">
                <p>
                  <strong>{selected.status} · source-reported</strong> at{" "}
                  {date(analysis.status_evidence.observed_at)} ·{" "}
                  {analysis.status_evidence.freshness}.{" "}
                  {analysis.status_evidence.reason}
                </p>
                <div className="research-facts">
                  <span>
                    <strong>{analysis.observations.count}</strong> observations
                  </span>
                  <span>
                    <strong>{analysis.observations.span_days}d</strong> observed
                    span
                  </span>
                  <span>
                    <strong>{analysis.creative_variants.count}</strong> text
                    variants
                  </span>
                  <span>
                    <strong>{analysis.advertiser.related_ads}</strong> ads by
                    this name
                  </span>
                </div>
                <h3>Creative angles, offers & calls to action</h3>
                {analysis.signals.length ? (
                  analysis.signals.map((signal, i) => (
                    <div className="metric" key={i}>
                      <strong>
                        {signal.category}: {signal.label.replaceAll("_", " ")}
                      </strong>
                      <p>
                        “{signal.excerpt}” · Creative{" "}
                        {signal.creative_index + 1}
                      </p>
                      <small>
                        English text rule · Confidence: {signal.confidence}
                      </small>
                    </div>
                  ))
                ) : (
                  <p>
                    No configured English text rules matched. This does not mean
                    the creative has no marketing angle.
                  </p>
                )}
                <p>
                  Source: {analysis.source.kind}.{" "}
                  {analysis.source.details?.coverage}
                </p>
                {analysis.source.details?.placements?.length ? (
                  <p>
                    Reported placements:{" "}
                    {analysis.source.details.placements.join(", ")}
                  </p>
                ) : null}
                {analysis.source.details?.media_urls?.map((url, i) => (
                  <p key={url}>
                    <a href={url} target="_blank" rel="noreferrer">
                      Source creative media {i + 1} <ExternalLink size={12} />
                    </a>
                  </p>
                ))}
                {analysis.limitations.map((note) => (
                  <p className="analysis-limitation" key={note}>
                    {note}
                  </p>
                ))}
              </div>
            )}
            <h3>Research signal score: {selected.score.value}/100</h3>
            <p className="muted">
              {selected.score.disclaimer} Confidence:{" "}
              {selected.score.confidence}.
            </p>
            {selected.score.components.map((m) => (
              <div className="metric" key={m.metric}>
                <strong>
                  {m.metric.replaceAll("_", " ")}{" "}
                  <span>
                    {m.value}/{m.maximum}
                  </span>
                </strong>
                <p>{m.evidence}</p>
                <small>
                  Source: {m.source} · Confidence: {m.confidence}
                </small>
              </div>
            ))}
            <h3>Creative text</h3>
            {selected.creatives.map((c, i) => (
              <p key={i}>{c.text}</p>
            ))}
            <h3>Raw evidence & provenance</h3>
            {evidence?.items.length ? (
              evidence.items.map((row) => (
                <details className="raw-evidence" key={row.id}>
                  <summary>
                    {row.source_id} · {date(row.observed_at)} · run {row.run_id}
                  </summary>
                  <p>
                    Rights reference: {row.rights_reference || "Demo/test data"}
                  </p>
                  <h4>Original record</h4>
                  <pre>{JSON.stringify(row.raw_data, null, 2)}</pre>
                  <h4>Normalized record</h4>
                  <pre>{JSON.stringify(row.normalized_data, null, 2)}</pre>
                </details>
              ))
            ) : (
              <p>No retained original file record for this legacy/demo ad.</p>
            )}
            {evidence && evidence.page * 10 < evidence.total && (
              <button
                className="secondary"
                onClick={() => {
                  void request<typeof evidence>(
                    `/ads/${selected.id}/evidence?data_mode=${dataMode}&page=${evidence.page + 1}`,
                  )
                    .then(setEvidence)
                    .catch((e) => setAnalysisError(String(e)));
                }}
              >
                More evidence
              </button>
            )}
            <h3>Observation history</h3>
            {history.map((h, i) => (
              <p key={i}>
                {date(h.observed_at)} · {h.status} ·{" "}
                <a href={h.source_url} target="_blank" rel="noreferrer">
                  source <ExternalLink size={12} />
                </a>
              </p>
            ))}
            <p>
              First seen {date(selected.first_seen)} · Last seen{" "}
              {date(selected.last_seen)}
            </p>
            <div className="detail-actions">
              <a
                href={selected.source_url || undefined}
                aria-disabled={!selected.source_url}
                target="_blank"
                rel="noreferrer"
              >
                Source URL <ExternalLink size={14} />
              </a>
              <a
                href={selected.landing_url || undefined}
                aria-disabled={!selected.landing_url}
                target="_blank"
                rel="noreferrer"
              >
                Landing URL <ExternalLink size={14} />
              </a>
              <button className="primary" onClick={() => void save(selected)}>
                {selected.saved ? <Check size={16} /> : <Bookmark size={16} />}{" "}
                {selected.saved ? "Saved" : "Save ad"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
