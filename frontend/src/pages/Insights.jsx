import React, { useEffect, useState } from "react";
import { api, formatINR } from "../lib/api";
import { toast } from "sonner";
import { Sparkles, AlertTriangle, TrendingUp, PiggyBank as Piggy, Moon, RefreshCw } from "lucide-react";

const SeverityChip = ({ s }) => {
  const map = { high: { c: "#EF4444", l: "High" }, medium: { c: "#F59E0B", l: "Medium" }, low: { c: "#60A5FA", l: "Low" } };
  const v = map[s] || map.medium;
  return <span className="overline" style={{ color: v.c }}>{v.l} risk</span>;
};

export default function Insights() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    setLoading(true);
    try { const r = await api.get("/insights"); setData(r.data); }
    catch (e) { toast.error("Failed to generate insights"); }
    finally { setLoading(false); setRefreshing(false); }
  };
  useEffect(() => { load(); }, []);

  const refresh = async () => { setRefreshing(true); await load(); toast.success("Insights refreshed"); };

  if (loading && !data) return <div className="text-secondary-muted" data-testid="insights-loading">Generating insights…</div>;

  return (
    <div className="space-y-8 fade-up" data-testid="insights-root">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="overline">AI Insights</div>
          <h1 className="font-display text-3xl md:text-4xl font-bold tracking-tight mt-1">Your money, <span className="text-brand">decoded</span></h1>
          <p className="text-[color:var(--text-secondary)] mt-2 max-w-xl">Rule-based + statistical detection + Claude Sonnet 4.5 summaries.</p>
        </div>
        <button onClick={refresh} disabled={refreshing} data-testid="insights-refresh-btn" className="btn-ghost inline-flex items-center gap-2 text-sm">
          <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      {/* AI Summary */}
      <div className="card-surface p-8 grain-overlay" data-testid="ai-summary-section">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg grid place-items-center shrink-0" style={{ background: "rgba(255,85,0,0.14)", color: "var(--brand)" }}>
            <Sparkles size={20} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="overline">AI coach · Claude Sonnet 4.5</div>
            <p className="text-[color:var(--text-primary)] mt-3 leading-relaxed whitespace-pre-wrap">
              {data?.ai_summary || "Add expenses to unlock personalized advice."}
            </p>
          </div>
        </div>
      </div>

      {/* Trend */}
      <div className="grid md:grid-cols-3 gap-6">
        <div className="card-surface p-6" data-testid="trend-card">
          <div className="overline">Month-over-month</div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-display text-3xl font-bold">{formatINR(data?.trend?.current_month_spend)}</span>
          </div>
          <div className="text-sm mt-1" style={{ color: data?.trend?.trend === "up" ? "#EF4444" : data?.trend?.trend === "down" ? "#10B981" : "#A1A1AA" }}>
            {data?.trend?.change_pct}% vs last month ({formatINR(data?.trend?.previous_month_spend)})
          </div>
        </div>
        <div className="card-surface p-6" data-testid="health-summary-card">
          <div className="overline">Health breakdown</div>
          <div className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-[color:var(--text-secondary)]">Savings rate</span><span className="font-semibold">{data?.health?.savings_rate}%</span></div>
            <div className="flex justify-between"><span className="text-[color:var(--text-secondary)]">Stability</span><span className="font-semibold">{data?.health?.stability}%</span></div>
            <div className="flex justify-between"><span className="text-[color:var(--text-secondary)]">Essentials ratio</span><span className="font-semibold">{data?.health?.essential_ratio}%</span></div>
          </div>
        </div>
        <div className="card-surface p-6" data-testid="anomaly-count-card">
          <div className="overline">Anomalies detected</div>
          <div className="font-display text-3xl font-bold mt-3">{data?.anomalies?.length || 0}</div>
          <div className="text-sm text-[color:var(--text-secondary)] mt-1">statistical outliers (z-score ≥ 2)</div>
        </div>
      </div>

      {/* Category overspending */}
      <Section title="Category overspending" icon={TrendingUp}>
        {(data?.category_overspends || []).length === 0 ? <Empty label="No categories overspending — nice!" /> :
          <div className="grid md:grid-cols-2 gap-4">
            {data.category_overspends.map((i, idx) => (
              <InsightBlock key={idx} title={i.category} severity={i.severity} message={i.message} testid={`overspend-${idx}`} />
            ))}
          </div>
        }
      </Section>

      {/* Savings opportunities */}
      <Section title="Savings opportunities" icon={Piggy}>
        {(data?.savings_opportunities || []).length === 0 ? <Empty label="No specific savings suggestions yet — keep adding expenses." /> :
          <div className="grid md:grid-cols-2 gap-4">
            {data.savings_opportunities.map((i, idx) => (
              <InsightBlock key={idx} title="Save more" severity={i.severity} message={i.message} testid={`savings-${idx}`} />
            ))}
          </div>
        }
      </Section>

      {/* Behavioral */}
      <Section title="Behavioral patterns" icon={Moon}>
        {(data?.behavioral_patterns || []).length === 0 ? <Empty label="No concerning patterns detected." /> :
          <div className="grid md:grid-cols-3 gap-4">
            {data.behavioral_patterns.map((i, idx) => (
              <InsightBlock key={idx} title={i.type.replace("_", " ")} capitalize severity={i.severity} message={i.message} testid={`behavior-${idx}`} />
            ))}
          </div>
        }
      </Section>

      {/* Anomalies */}
      <Section title="Anomalies" icon={AlertTriangle}>
        {(data?.anomalies || []).length === 0 ? <Empty label="No unusual transactions." /> :
          <div className="card-surface p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-[color:var(--text-muted)] border-b" style={{ borderColor: "var(--border)" }}>
                <th className="px-4 py-3">Date</th><th className="px-4 py-3">Merchant</th><th className="px-4 py-3">Category</th><th className="px-4 py-3 text-right">Amount</th><th className="px-4 py-3">Why flagged</th>
              </tr></thead>
              <tbody>
                {data.anomalies.map((a, i) => (
                  <tr key={i} className="border-b" style={{ borderColor: "var(--border)" }} data-testid={`anomaly-row-${i}`}>
                    <td className="px-4 py-3 text-[color:var(--text-secondary)]">{(a.date || "").slice(0, 10)}</td>
                    <td className="px-4 py-3">{a.merchant || "—"}</td>
                    <td className="px-4 py-3">{a.category}</td>
                    <td className="px-4 py-3 text-right font-semibold">{formatINR(a.amount)}</td>
                    <td className="px-4 py-3 text-[color:var(--text-secondary)]">{a.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        }
      </Section>
    </div>
  );
}

const Section = ({ title, icon: Icon, children }) => (
  <div>
    <div className="flex items-center gap-2 mb-4">
      <Icon size={18} className="text-brand" />
      <h2 className="font-display text-xl font-semibold">{title}</h2>
    </div>
    {children}
  </div>
);

const InsightBlock = ({ title, severity, message, capitalize, testid }) => (
  <div className="card-surface p-5" data-testid={testid}>
    <div className="flex items-center gap-2 mb-2"><SeverityChip s={severity} /></div>
    <div className={`font-display font-semibold text-lg ${capitalize ? "capitalize" : ""}`}>{title}</div>
    <p className="text-sm text-[color:var(--text-secondary)] mt-2 leading-relaxed">{message}</p>
  </div>
);

const Empty = ({ label }) => (
  <div className="card-surface p-8 text-center text-sm text-[color:var(--text-secondary)]">{label}</div>
);
