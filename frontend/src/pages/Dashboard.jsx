import React, { useEffect, useState } from "react";
import { api, formatINR } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";
import { Sparkles, TrendingUp, TrendingDown, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

const CHART_COLORS = ["#FF5500", "#00E5FF", "#10B981", "#F59E0B", "#A855F7", "#EC4899", "#60A5FA", "#FB923C"];

function HealthRing({ score }) {
  const radius = 70;
  const circ = 2 * Math.PI * radius;
  const pct = Math.min(100, Math.max(0, score));
  const offset = circ - (pct / 100) * circ;
  const color = pct >= 70 ? "#10B981" : pct >= 40 ? "#F59E0B" : "#EF4444";
  return (
    <div className="relative w-[180px] h-[180px]" data-testid="health-score-ring">
      <svg width="180" height="180" viewBox="0 0 180 180">
        <circle cx="90" cy="90" r={radius} stroke="#27272A" strokeWidth="12" fill="none" />
        <circle cx="90" cy="90" r={radius} stroke={color} strokeWidth="12" fill="none"
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
          transform="rotate(-90 90 90)" style={{ transition: "stroke-dashoffset 700ms ease-out" }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center">
        <div className="text-center">
          <div className="font-display text-4xl font-bold" style={{ color }}>{score}</div>
          <div className="overline">of 100</div>
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [summary, setSummary] = useState(null);
  const [insights, setInsights] = useState(null);
  const [aiSummary, setAiSummary] = useState(null);
  const [aiLoading, setAiLoading] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Fast first paint: summary + quick insights (no LLM)
        const [s, q] = await Promise.all([
          api.get("/expenses/summary"),
          api.get("/insights/quick"),
        ]);
        if (cancelled) return;
        setSummary(s.data);
        setInsights(q.data);
      } catch (e) {
        console.error(e);
      } finally { if (!cancelled) setLoading(false); }

      // Defer AI summary — uses cached LLM if recent
      try {
        const ai = await api.get("/insights");
        if (cancelled) return;
        setAiSummary(ai.data?.ai_summary);
      } catch (e) {
        // graceful
      } finally { if (!cancelled) setAiLoading(false); }
    })();
    return () => { cancelled = true; };
  }, []);

  if (loading) return <div className="text-secondary-muted" data-testid="dashboard-loading">Loading your dashboard…</div>;

  const trend = summary?.health?.savings_rate >= 0 ? "up" : "down";
  const healthColor = summary?.health?.score >= 70 ? "text-green-400" : summary?.health?.score >= 40 ? "text-yellow-400" : "text-red-400";
  const trendData = summary?.daily_trend || [];
  const topCats = summary?.top_categories || [];

  return (
    <div className="space-y-8 fade-up" data-testid="dashboard-root">
      <div>
        <div className="overline">Welcome back</div>
        <h1 className="font-display text-3xl md:text-5xl font-bold tracking-tight mt-1">
          Hi {user?.name?.split(" ")[0]}, <span className="text-brand">here's your money snapshot.</span>
        </h1>
      </div>

      {/* Health Score + KPIs */}
      <div className="grid md:grid-cols-3 lg:grid-cols-4 gap-6">
        <div className="card-surface p-8 md:col-span-2 lg:col-span-2 flex items-center gap-8" data-testid="health-score-card">
          <HealthRing score={summary?.health?.score ?? 0} />
          <div className="flex-1 min-w-0">
            <div className="overline mb-1">Financial Health Score</div>
            <h3 className="font-display text-2xl font-semibold">Your money fitness</h3>
            <p className="text-sm text-[color:var(--text-secondary)] mt-2 leading-relaxed">
              Based on your savings rate ({summary?.health?.savings_rate}%), spending stability and essential-vs-want mix.
            </p>
            <Link to="/app/insights" data-testid="health-see-insights" className="inline-flex items-center gap-2 mt-4 text-sm text-brand font-semibold">
              See insights <ArrowRight size={14} />
            </Link>
          </div>
        </div>

        <div className="card-surface p-6" data-testid="kpi-month-spend">
          <div className="overline">Last 30 days</div>
          <div className="font-display text-3xl font-bold mt-2">{formatINR(summary?.window_total ?? summary?.health?.total_spend_this_month)}</div>
          <div className="text-xs text-[color:var(--text-secondary)] mt-1">Total spent</div>
          <div className="mt-4 pt-4 border-t" style={{ borderColor: "var(--border)" }}>
            <div className="flex items-center gap-2 text-sm">
              {insights?.trend?.trend === "up" ? <TrendingUp size={16} className="text-red-400" /> : <TrendingDown size={16} className="text-green-400" />}
              <span className={insights?.trend?.trend === "up" ? "text-red-400" : "text-green-400"}>
                {insights?.trend?.change_pct}% vs last month
              </span>
            </div>
          </div>
        </div>

        <div className="card-surface p-6" data-testid="kpi-savings-rate">
          <div className="overline">Savings rate</div>
          <div className={`font-display text-3xl font-bold mt-2 ${healthColor}`}>{summary?.health?.savings_rate}%</div>
          <div className="text-xs text-[color:var(--text-secondary)] mt-1">of income</div>
          {(!user?.monthly_income) && (
            <Link to="/app/settings" data-testid="set-income-link" className="mt-4 text-xs text-brand font-semibold inline-flex items-center gap-1">
              Set your income <ArrowRight size={12} />
            </Link>
          )}
        </div>
      </div>

      {/* Charts */}
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="card-surface p-6 lg:col-span-2" data-testid="trend-chart-card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="overline">Last 30 days</div>
              <h3 className="font-display text-xl font-semibold mt-1">Daily spend</h3>
            </div>
          </div>
          <div style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer>
              <LineChart data={trendData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <XAxis dataKey="date" stroke="#71717A" tick={{ fontSize: 11 }} tickFormatter={(d) => d.slice(8)} />
                <YAxis stroke="#71717A" tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: "#121316", border: "1px solid #27272A", borderRadius: 8, color: "#F8F9FA" }}
                  formatter={(v) => formatINR(v)}
                />
                <Line type="monotone" dataKey="amount" stroke="#FF5500" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card-surface p-6" data-testid="category-donut-card">
          <div className="overline">Top categories · 30d</div>
          <h3 className="font-display text-xl font-semibold mt-1 mb-4">Where it goes</h3>
          {topCats.length === 0 ? (
            <div className="text-sm text-[color:var(--text-secondary)] py-8 text-center">No expenses yet.</div>
          ) : (
            <>
              <div style={{ width: "100%", height: 200 }}>
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={topCats.slice(0, 6)} dataKey="amount" nameKey="category" innerRadius={55} outerRadius={80} paddingAngle={3}>
                      {topCats.slice(0, 6).map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                    </Pie>
                    <Tooltip contentStyle={{ background: "#121316", border: "1px solid #27272A", borderRadius: 8, color: "#F8F9FA" }} formatter={(v) => formatINR(v)} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-4 space-y-2">
                {topCats.slice(0, 5).map((c, i) => (
                  <div key={c.category} className="flex items-center justify-between text-sm" data-testid={`top-cat-${i}`}>
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
                      <span className="text-[color:var(--text-secondary)]">{c.category}</span>
                    </div>
                    <span className="font-medium">{formatINR(c.amount)}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* AI Summary */}
      <div className="card-surface p-8 grain-overlay" data-testid="ai-summary-card">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg grid place-items-center shrink-0" style={{ background: "rgba(255,85,0,0.14)", color: "var(--brand)" }}>
            <Sparkles size={20} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="overline">AI Summary · Claude</div>
            <h3 className="font-display text-xl font-semibold mt-1">This week in your money</h3>
            {aiLoading && !aiSummary ? (
              <div className="mt-3 space-y-2" data-testid="ai-summary-skeleton">
                <div className="h-3 w-11/12 rounded" style={{ background: "var(--bg-surface-hover)" }} />
                <div className="h-3 w-9/12 rounded" style={{ background: "var(--bg-surface-hover)" }} />
                <div className="h-3 w-10/12 rounded" style={{ background: "var(--bg-surface-hover)" }} />
                <div className="text-xs text-[color:var(--text-muted)] mt-2">AI coach is thinking…</div>
              </div>
            ) : (
              <p className="text-[color:var(--text-secondary)] mt-3 leading-relaxed whitespace-pre-wrap">
                {aiSummary || "Add some expenses to get your first AI-powered summary."}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Quick insights */}
      <div className="grid md:grid-cols-2 gap-6">
        {(insights?.category_overspends?.slice(0, 2) || []).map((i, idx) => (
          <div key={idx} className="card-surface p-6" data-testid={`overspend-card-${idx}`}>
            <div className="flex items-center gap-2 mb-2">
              <span className="overline" style={{ color: i.severity === "high" ? "#EF4444" : "#F59E0B" }}>{i.severity} risk</span>
            </div>
            <div className="font-display font-semibold text-lg">{i.category}</div>
            <p className="text-sm text-[color:var(--text-secondary)] mt-2">{i.message}</p>
          </div>
        ))}
        {(insights?.behavioral_patterns?.slice(0, 2) || []).map((i, idx) => (
          <div key={`b${idx}`} className="card-surface p-6" data-testid={`behavior-card-${idx}`}>
            <div className="flex items-center gap-2 mb-2">
              <span className="overline text-brand">Behavior</span>
            </div>
            <div className="font-display font-semibold text-lg capitalize">{i.type.replace("_", " ")}</div>
            <p className="text-sm text-[color:var(--text-secondary)] mt-2">{i.message}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
