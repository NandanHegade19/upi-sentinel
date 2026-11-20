import React, { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  CartesianGrid,
} from "recharts";

interface AdminBIDashboardProps {
  apiBaseUrl: string;
  userRole: string;
}

interface MetricsData {
  kpis: {
    total_txns: number;
    total_volume_inr: number;
    pending_volume_inr: number;
    issue_count: number;
    issue_rate_pct: number;
  };
  rail_health: {
    rail: string;
    success: number;
    pending: number;
    failed: number;
    total_volume_inr: number;
  }[];
  root_causes: {
    reason: string;
    count: number;
  }[];
  approvals: {
    action_type: string;
    status: string;
    count: number;
  }[];
}

interface TextToSQLResult {
  prompt: string;
  generated_sql: string;
  columns: string[];
  rows: Record<string, any>[];
  row_count: number;
  execution_ms: number;
}

const PIE_COLORS = ["#ef4444", "#f97316", "#eab308", "#8b5cf6", "#3b82f6", "#14b8a6"];

const DEMO_PROMPTS = [
  "Show total INR value stuck in PENDING grouped by payment rail",
  "List the top 5 highest-value FAILED transactions",
  "Count all approval requests by action type and status",
  "Show top 5 failure response codes from txn_event",
];

const formatINR = (amount: number) => {
  if (amount >= 1e7) return `₹${(amount / 1e7).toFixed(2)} Cr`;
  if (amount >= 1e5) return `₹${(amount / 1e5).toFixed(2)} L`;
  return `₹${amount.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
};

const cardStyle: React.CSSProperties = {
  backgroundColor: "var(--bg-panel, #111827)",
  border: "1px solid var(--border-color, #1f2937)",
  borderRadius: "12px",
  padding: "20px",
};

export const AdminBIDashboard: React.FC<AdminBIDashboardProps> = ({
  apiBaseUrl,
  userRole,
}) => {
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [loadingMetrics, setLoadingMetrics] = useState(true);
  const [metricsError, setMetricsError] = useState<string | null>(null);

  const [prompt, setPrompt] = useState(DEMO_PROMPTS[0]);
  const [sqlResult, setSqlResult] = useState<TextToSQLResult | null>(null);
  const [loadingSql, setLoadingSql] = useState(false);
  const [sqlError, setSqlError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"table" | "chart">("table");

  useEffect(() => {
    const fetchMetrics = async () => {
      setLoadingMetrics(true);
      setMetricsError(null);
      try {
        const res = await fetch(`${apiBaseUrl}/api/v1/admin/metrics`, {
          headers: { "X-User-Role": userRole },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setMetrics(data);
      } catch (err: any) {
        setMetricsError(err.message || "Failed to load BI metrics");
      } finally {
        setLoadingMetrics(false);
      }
    };
    fetchMetrics();
  }, [apiBaseUrl, userRole]);

  const runTextToSql = async (queryText?: string) => {
    const activePrompt = (queryText ?? prompt).trim();
    if (!activePrompt) return;
    if (queryText) setPrompt(queryText);

    setLoadingSql(true);
    setSqlError(null);
    setSqlResult(null);

    try {
      const res = await fetch(`${apiBaseUrl}/api/v1/admin/text-to-sql`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-Role": userRole,
        },
        body: JSON.stringify({ prompt: activePrompt }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Error ${res.status}`);
      }
      setSqlResult(data);
      setViewMode("table");
    } catch (err: any) {
      setSqlError(err.message || "Failed to execute Text-to-SQL query");
    } finally {
      setLoadingSql(false);
    }
  };

  const canAutoChart =
    sqlResult &&
    sqlResult.columns.length === 2 &&
    sqlResult.rows.length > 0 &&
    !isNaN(Number(sqlResult.rows[0][sqlResult.columns[1]]));

  const autoChartData = canAutoChart
    ? sqlResult!.rows.map((r) => ({
        label: String(r[sqlResult!.columns[0]]),
        value: Number(r[sqlResult!.columns[1]]),
      }))
    : [];

  return (
    <div style={{ padding: "24px", color: "#f1f5f9", maxWidth: "1400px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "24px" }}>
      
      {/* HEADER */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border-color, #1f2937)", paddingBottom: "16px", flexWrap: "wrap", gap: "12px" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: "24px", fontWeight: 700 }}>Admin & BI Analytics</h1>
          <p style={{ margin: "4px 0 0", fontSize: "13px", color: "#94a3b8" }}>
            Live PostgreSQL operational metrics & read-only AI Text-to-SQL explorer
          </p>
        </div>
        <span style={{ padding: "6px 14px", borderRadius: "999px", fontSize: "12px", backgroundColor: "#1e293b", border: "1px solid #334155", color: "#cbd5e1" }}>
          Role: <strong style={{ color: "#10b981" }}>{userRole}</strong>
        </span>
      </div>

      {/* KPI CARDS */}
      {loadingMetrics ? (
        <div style={{ color: "#94a3b8", fontSize: "14px" }}>Loading live metrics...</div>
      ) : metricsError ? (
        <div style={{ padding: "14px", borderRadius: "8px", backgroundColor: "rgba(127, 29, 29, 0.35)", border: "1px solid #991b1b", color: "#fca5a5", fontSize: "13px" }}>
          {metricsError}
        </div>
      ) : metrics ? (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px" }}>
            <div style={cardStyle}>
              <div style={{ fontSize: "11px", textTransform: "uppercase", color: "#94a3b8", letterSpacing: "0.05em" }}>Total Volume</div>
              <div style={{ fontSize: "28px", fontWeight: 700, color: "#10b981", marginTop: "6px" }}>
                {formatINR(metrics.kpis.total_volume_inr)}
              </div>
              <div style={{ fontSize: "12px", color: "#64748b", marginTop: "4px" }}>
                {metrics.kpis.total_txns.toLocaleString()} transactions
              </div>
            </div>

            <div style={cardStyle}>
              <div style={{ fontSize: "11px", textTransform: "uppercase", color: "#94a3b8", letterSpacing: "0.05em" }}>Stuck in Pending</div>
              <div style={{ fontSize: "28px", fontWeight: 700, color: "#f59e0b", marginTop: "6px" }}>
                {formatINR(metrics.kpis.pending_volume_inr)}
              </div>
              <div style={{ fontSize: "12px", color: "#64748b", marginTop: "4px" }}>
                Requires reconciliation
              </div>
            </div>

            <div style={cardStyle}>
              <div style={{ fontSize: "11px", textTransform: "uppercase", color: "#94a3b8", letterSpacing: "0.05em" }}>Failure / Pending Rate</div>
              <div style={{ fontSize: "28px", fontWeight: 700, color: "#f43f5e", marginTop: "6px" }}>
                {metrics.kpis.issue_rate_pct}%
              </div>
              <div style={{ fontSize: "12px", color: "#64748b", marginTop: "4px" }}>
                {metrics.kpis.issue_count} impacted txns
              </div>
            </div>

            <div style={cardStyle}>
              <div style={{ fontSize: "11px", textTransform: "uppercase", color: "#94a3b8", letterSpacing: "0.05em" }}>Approval Queue</div>
              <div style={{ fontSize: "28px", fontWeight: 700, color: "#38bdf8", marginTop: "6px" }}>
                {metrics.approvals.reduce((acc, a) => acc + a.count, 0)}
              </div>
              <div style={{ fontSize: "12px", color: "#64748b", marginTop: "4px" }}>
                {metrics.approvals.map((a) => `${a.action_type}: ${a.count}`).join(" · ") || "None"}
              </div>
            </div>
          </div>

          {/* CHARTS ROW */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: "20px" }}>
            <div style={cardStyle}>
              <h2 style={{ margin: "0 0 16px", fontSize: "15px", fontWeight: 600, color: "#e2e8f0" }}>
                Payment Rail Health (Transaction Counts)
              </h2>
              <div style={{ width: "100%", height: "280px" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={metrics.rail_health}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="rail" stroke="#94a3b8" fontSize={12} />
                    <YAxis stroke="#94a3b8" fontSize={12} />
                    <Tooltip cursor={{ fill: "rgba(148, 163, 184, 0.1)" }} 
                    contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", borderRadius: "8px" }} />
                    <Legend />
                    <Bar dataKey="success" stackId="a" fill="#10b981" name="Success" />
                    <Bar dataKey="pending" stackId="a" fill="#f59e0b" name="Pending" />
                    <Bar dataKey="failed" stackId="a" fill="#ef4444" name="Failed" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div style={cardStyle}>
              <h2 style={{ margin: "0 0 16px", fontSize: "15px", fontWeight: 600, color: "#e2e8f0" }}>
                Top Failure & Timeout Root Causes
              </h2>
              <div style={{ width: "100%", height: "280px" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={metrics.root_causes}
                      dataKey="count"
                      nameKey="reason"
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={95}
                      paddingAngle={3}
                    >
                      {metrics.root_causes.map((_, idx) => (
                        <Cell key={idx} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", borderRadius: "8px" }} />
                    <Legend wrapperStyle={{ fontSize: "11px" }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </>
      ) : null}

      {/* AI PROMPT-TO-SQL EXPLORER */}
      <div style={{ ...cardStyle, display: "flex", flexDirection: "column", gap: "16px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
          <div>
            <h2 style={{ margin: 0, fontSize: "16px", fontWeight: 600, color: "#f1f5f9" }}>
              AI Prompt-to-SQL Explorer
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: "12px", color: "#94a3b8" }}>
              Ask questions in plain English. Protected by READ ONLY transactions, 3s timeout, and RBAC.
            </p>
          </div>
          <span style={{ fontSize: "12px", padding: "4px 10px", borderRadius: "6px", backgroundColor: "rgba(6, 78, 59, 0.5)", border: "1px solid #065f46", color: "#6ee7b7" }}>
            Guardrails Active: SELECT-Only
          </span>
        </div>

        {/* DEMO CHIPS */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
          {DEMO_PROMPTS.map((chip) => (
            <button
              key={chip}
              onClick={() => runTextToSql(chip)}
              style={{
                fontSize: "12px",
                padding: "6px 12px",
                borderRadius: "999px",
                backgroundColor: "#1e293b",
                border: "1px solid #334155",
                color: "#cbd5e1",
                cursor: "pointer",
              }}
            >
              {chip}
            </button>
          ))}
        </div>

        {/* INPUT BAR */}
        <div style={{ display: "flex", gap: "10px" }}>
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runTextToSql()}
            placeholder="e.g., Show top 5 failed UPI transactions over 10,000 INR..."
            style={{
              flex: 1,
              padding: "10px 14px",
              borderRadius: "8px",
              backgroundColor: "#0b1120",
              border: "1px solid #334155",
              color: "#f8fafc",
              fontSize: "13px",
              outline: "none",
            }}
          />
          <button
            onClick={() => runTextToSql()}
            disabled={loadingSql}
            style={{
              padding: "10px 20px",
              borderRadius: "8px",
              backgroundColor: loadingSql ? "#047857" : "#10b981",
              border: "none",
              color: "#ffffff",
              fontSize: "13px",
              fontWeight: 600,
              cursor: loadingSql ? "not-allowed" : "pointer",
            }}
          >
            {loadingSql ? "Running..." : "Run SQL"}
          </button>
        </div>

        {/* ERROR BANNER */}
        {sqlError && (
          <div style={{ padding: "12px", borderRadius: "8px", backgroundColor: "rgba(127, 29, 29, 0.4)", border: "1px solid #991b1b", color: "#fca5a5", fontSize: "12px" }}>
            {sqlError}
          </div>
        )}

        {/* SQL RESULT */}
        {sqlResult && (
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <div style={{ backgroundColor: "#0b1120", border: "1px solid #1e293b", borderRadius: "8px", padding: "14px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "#94a3b8", marginBottom: "8px" }}>
                <span>Generated PostgreSQL</span>
                <span>{sqlResult.row_count} rows · {sqlResult.execution_ms} ms</span>
              </div>
              <pre style={{ margin: 0, fontSize: "12px", color: "#34d399", overflowX: "auto", fontFamily: "monospace" }}>
                {sqlResult.generated_sql}
              </pre>
            </div>

            {canAutoChart && (
              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  onClick={() => setViewMode("table")}
                  style={{
                    padding: "6px 14px",
                    fontSize: "12px",
                    borderRadius: "6px",
                    cursor: "pointer",
                    backgroundColor: viewMode === "table" ? "#1e293b" : "transparent",
                    border: viewMode === "table" ? "1px solid #10b981" : "1px solid #334155",
                    color: viewMode === "table" ? "#ffffff" : "#94a3b8",
                  }}
                >
                  Table View
                </button>
                <button
                  onClick={() => setViewMode("chart")}
                  style={{
                    padding: "6px 14px",
                    fontSize: "12px",
                    borderRadius: "6px",
                    cursor: "pointer",
                    backgroundColor: viewMode === "chart" ? "#1e293b" : "transparent",
                    border: viewMode === "chart" ? "1px solid #10b981" : "1px solid #334155",
                    color: viewMode === "chart" ? "#ffffff" : "#94a3b8",
                  }}
                >
                  Auto-Chart View
                </button>
              </div>
            )}

            {viewMode === "chart" && canAutoChart ? (
              <div style={{ width: "100%", height: "280px", backgroundColor: "#0b1120", border: "1px solid #1e293b", borderRadius: "8px", padding: "16px", boxSizing: "border-box" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={autoChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="label" stroke="#94a3b8" fontSize={12} />
                    <YAxis stroke="#94a3b8" fontSize={12} />
                    <Tooltip cursor={{ fill: "rgba(148, 163, 184, 0.1)" }} contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", borderRadius: "8px" }} />
                    <Bar dataKey="value" fill="#38bdf8" name={sqlResult.columns[1]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div style={{ overflowX: "auto", borderRadius: "8px", border: "1px solid #1e293b" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "13px" }}>
                  <thead>
                    <tr style={{ backgroundColor: "#0b1120", color: "#94a3b8", borderBottom: "1px solid #1e293b" }}>
                      {sqlResult.columns.map((col) => (
                        <th key={col} style={{ padding: "10px 14px", fontWeight: 600, textTransform: "uppercase", fontSize: "11px" }}>
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sqlResult.rows.map((row, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid #1e293b" }}>
                        {sqlResult.columns.map((col) => (
                          <td key={col} style={{ padding: "10px 14px", color: "#e2e8f0", fontFamily: "monospace" }}>
                            {typeof row[col] === "object" && row[col] !== null
                              ? JSON.stringify(row[col])
                              : String(row[col] ?? "—")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};