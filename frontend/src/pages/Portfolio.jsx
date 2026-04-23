import React, { useEffect, useState } from "react";
import { api, formatINR } from "../lib/api";
import { toast } from "sonner";
import { Plus, RefreshCw, Trash2, Search } from "lucide-react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

const SECTORS = ["Technology", "Financial Services", "FMCG", "Pharma", "Auto", "Energy", "Real Estate", "Metals", "Telecom", "Consumer", "Other"];
const COLORS = ["#FF5500", "#00E5FF", "#10B981", "#F59E0B", "#A855F7", "#EC4899", "#60A5FA", "#FB923C", "#84CC16", "#F472B6", "#94A3B8"];

export default function Portfolio() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    setLoading(true);
    try { const r = await api.get("/portfolio"); setData(r.data); }
    catch { toast.error("Failed to load portfolio"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const refresh = async () => {
    setRefreshing(true);
    try { await api.post("/portfolio/refresh-prices"); toast.success("Prices refreshed"); await load(); }
    catch { toast.error("Refresh failed"); }
    finally { setRefreshing(false); }
  };

  const onDelete = async (id) => {
    if (!window.confirm("Remove this holding?")) return;
    try { await api.delete(`/portfolio/${id}`); toast.success("Removed"); load(); } catch { toast.error("Failed"); }
  };

  if (loading && !data) return <div className="text-secondary-muted" data-testid="portfolio-loading">Loading portfolio…</div>;

  const alloc = (data?.allocation_by_sector || []).filter(a => a.value > 0);

  return (
    <div className="space-y-8 fade-up" data-testid="portfolio-root">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="overline">Investments</div>
          <h1 className="font-display text-3xl md:text-4xl font-bold tracking-tight mt-1">Your portfolio</h1>
          <p className="text-[color:var(--text-secondary)] mt-2 max-w-xl">Live NAV from AMFI + stock prices from Yahoo. Cached for 6 hours.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={refresh} disabled={refreshing} data-testid="portfolio-refresh-btn" className="btn-ghost inline-flex items-center gap-2 text-sm">
            <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} /> Refresh prices
          </button>
          <button onClick={() => setModalOpen(true)} data-testid="portfolio-add-btn" className="btn-primary inline-flex items-center gap-2 text-sm">
            <Plus size={16} /> Add holding
          </button>
        </div>
      </div>

      {/* Summary KPIs */}
      <div className="grid md:grid-cols-4 gap-6">
        <KPI label="Invested" value={formatINR(data?.summary?.total_invested)} testid="kpi-invested" />
        <KPI label="Current value" value={formatINR(data?.summary?.total_current)} testid="kpi-current" />
        <KPI label="P&L" value={formatINR(data?.summary?.total_pnl)}
          sub={`${data?.summary?.total_pnl_pct || 0}%`}
          valueClass={(data?.summary?.total_pnl || 0) >= 0 ? "text-green-400" : "text-red-400"}
          testid="kpi-pnl" />
        <KPI label="Holdings" value={data?.summary?.holding_count || 0} testid="kpi-holdings" />
      </div>

      {/* Risk signals */}
      {(data?.risk_signals || []).length > 0 && (
        <div className="grid md:grid-cols-2 gap-4" data-testid="risk-signals">
          {data.risk_signals.map((r, i) => (
            <div key={i} className="card-surface p-5" data-testid={`risk-${i}`}>
              <div className="overline" style={{ color: r.severity === "high" ? "#EF4444" : "#F59E0B" }}>{r.severity} risk</div>
              <p className="text-sm text-[color:var(--text-primary)] mt-2">{r.message}</p>
            </div>
          ))}
        </div>
      )}

      {/* Allocation + table */}
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="card-surface p-6" data-testid="allocation-card">
          <div className="overline">Allocation by sector</div>
          <h3 className="font-display text-lg font-semibold mt-1 mb-4">How you're spread</h3>
          {alloc.length === 0 ? <div className="text-sm text-[color:var(--text-secondary)] py-8 text-center">Add holdings to see allocation.</div> :
          <>
            <div style={{ width: "100%", height: 220 }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={alloc} dataKey="value" nameKey="sector" innerRadius={60} outerRadius={90} paddingAngle={2}>
                    {alloc.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#121316", border: "1px solid #27272A", borderRadius: 8, color: "#F8F9FA" }} formatter={(v) => formatINR(v)} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4 space-y-2">
              {alloc.map((a, i) => (
                <div key={a.sector} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full" style={{ background: COLORS[i % COLORS.length] }} /><span className="text-[color:var(--text-secondary)]">{a.sector}</span></div>
                  <span className="font-medium">{a.pct}%</span>
                </div>
              ))}
            </div>
          </>}
        </div>

        <div className="card-surface lg:col-span-2 overflow-hidden" data-testid="holdings-table">
          {(data?.holdings || []).length === 0 ? (
            <div className="p-10 text-center">
              <div className="text-[color:var(--text-secondary)] mb-2">No holdings yet.</div>
              <p className="text-sm text-[color:var(--text-muted)]">Add your first stock or mutual fund to get started.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[720px]">
              <thead>
                <tr className="text-left text-[color:var(--text-muted)] border-b" style={{ borderColor: "var(--border)" }}>
                  <th className="px-4 py-3 font-medium">Asset</th>
                  <th className="px-4 py-3 font-medium">Qty</th>
                  <th className="px-4 py-3 font-medium text-right">Avg buy</th>
                  <th className="px-4 py-3 font-medium text-right">LTP</th>
                  <th className="px-4 py-3 font-medium text-right">Current</th>
                  <th className="px-4 py-3 font-medium text-right">P&L</th>
                  <th className="px-4 py-3 w-12"></th>
                </tr>
              </thead>
              <tbody>
                {data.holdings.map((h) => (
                  <tr key={h.id} className="border-b hover:bg-[color:var(--bg-surface-hover)]" style={{ borderColor: "var(--border)" }} data-testid={`holding-row-${h.id}`}>
                    <td className="px-4 py-3">
                      <div className="font-medium">{h.symbol}</div>
                      <div className="text-xs text-[color:var(--text-muted)]">
                        {h.asset_type === "mf" ? "Mutual Fund" : "Stock"}{h.is_sip && " · SIP"}
                        {h.name && h.name !== h.symbol ? ` · ${h.name.slice(0, 30)}` : ""}
                      </div>
                    </td>
                    <td className="px-4 py-3">{h.quantity}</td>
                    <td className="px-4 py-3 text-right">{formatINR(h.avg_buy_price)}</td>
                    <td className="px-4 py-3 text-right">{formatINR(h.current_price)}</td>
                    <td className="px-4 py-3 text-right font-semibold">{formatINR(h.current_value)}</td>
                    <td className={`px-4 py-3 text-right font-semibold ${h.pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {formatINR(h.pnl)} <span className="text-xs">({h.pnl_pct}%)</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => onDelete(h.id)} data-testid={`holding-delete-${h.id}`} className="text-[color:var(--text-muted)] hover:text-red-400"><Trash2 size={16} /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </div>
      </div>

      {modalOpen && <AddHoldingModal onClose={() => setModalOpen(false)} onAdded={() => { setModalOpen(false); load(); }} />}
    </div>
  );
}

const KPI = ({ label, value, sub, valueClass = "", testid }) => (
  <div className="card-surface p-6" data-testid={testid}>
    <div className="overline">{label}</div>
    <div className={`font-display text-2xl md:text-3xl font-bold mt-2 ${valueClass}`}>{value}</div>
    {sub && <div className="text-sm text-[color:var(--text-secondary)] mt-1">{sub}</div>}
  </div>
);

function AddHoldingModal({ onClose, onAdded }) {
  const [type, setType] = useState("stock");
  const [form, setForm] = useState({ symbol: "", name: "", quantity: "", avg_buy_price: "", sector: "Other", is_sip: false, sip_amount: 0 });
  const [mfResults, setMfResults] = useState([]);
  const [mfQuery, setMfQuery] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const searchMF = async () => {
    if (!mfQuery.trim()) return;
    try { const r = await api.get(`/prices/mf/search?q=${encodeURIComponent(mfQuery)}`); setMfResults(r.data.results); }
    catch { toast.error("Search failed"); }
  };

  const pickMF = (m) => {
    setForm({ ...form, symbol: m.scheme_code, name: m.scheme_name, avg_buy_price: m.nav });
    setMfResults([]);
    setMfQuery(m.scheme_name);
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post("/portfolio", {
        asset_type: type,
        symbol: form.symbol,
        name: form.name,
        quantity: Number(form.quantity),
        avg_buy_price: Number(form.avg_buy_price),
        sector: form.sector,
        is_sip: form.is_sip,
        sip_amount: Number(form.sip_amount || 0),
      });
      toast.success("Holding added");
      onAdded();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
    finally { setSubmitting(false); }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 grid place-items-center p-4" onClick={onClose} data-testid="add-holding-modal">
      <form onClick={(e) => e.stopPropagation()} onSubmit={onSubmit} className="card-surface p-6 w-full max-w-lg space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-xl font-semibold">Add holding</h2>
          <button type="button" onClick={onClose} data-testid="close-modal-btn" className="text-[color:var(--text-muted)]">✕</button>
        </div>

        <div className="flex gap-2">
          {["stock", "mf"].map((t) => (
            <button type="button" key={t} onClick={() => setType(t)} data-testid={`type-${t}`}
              className={`px-4 py-2 rounded-lg text-sm border ${type === t ? "border-[color:var(--brand)] bg-[rgba(255,85,0,0.1)] text-white" : "border-[color:var(--border)] text-[color:var(--text-secondary)]"}`}>
              {t === "stock" ? "Stock" : "Mutual Fund"}
            </button>
          ))}
        </div>

        {type === "mf" ? (
          <div>
            <label className="text-sm">Search fund</label>
            <div className="flex gap-2 mt-1">
              <input value={mfQuery} onChange={(e) => setMfQuery(e.target.value)}
                placeholder="e.g. Parag Parikh Flexi"
                data-testid="mf-search-input"
                className="flex-1 bg-transparent border rounded-lg px-3 py-2.5 outline-none" style={{ borderColor: "var(--border)" }} />
              <button type="button" onClick={searchMF} data-testid="mf-search-btn" className="btn-ghost inline-flex items-center gap-2"><Search size={16} /></button>
            </div>
            {mfResults.length > 0 && (
              <div className="mt-2 max-h-40 overflow-auto border rounded-lg" style={{ borderColor: "var(--border)" }}>
                {mfResults.map((m) => (
                  <button type="button" key={m.scheme_code} onClick={() => pickMF(m)}
                    data-testid={`mf-result-${m.scheme_code}`}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-[color:var(--bg-surface-hover)]">
                    <div className="truncate">{m.scheme_name}</div>
                    <div className="text-xs text-[color:var(--text-muted)]">NAV ₹{m.nav} · {m.scheme_code}</div>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <Field label="Ticker symbol (e.g. RELIANCE, INFY)">
            <input required value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value })}
              data-testid="stock-symbol-input"
              className="w-full bg-transparent border rounded-lg px-3 py-2.5 outline-none" style={{ borderColor: "var(--border)" }} />
          </Field>
        )}

        <div className="grid grid-cols-2 gap-3">
          <Field label="Quantity">
            <input required type="number" step="0.001" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })}
              data-testid="holding-quantity-input"
              className="w-full bg-transparent border rounded-lg px-3 py-2.5 outline-none" style={{ borderColor: "var(--border)" }} />
          </Field>
          <Field label="Avg buy price (₹)">
            <input required type="number" step="0.01" value={form.avg_buy_price} onChange={(e) => setForm({ ...form, avg_buy_price: e.target.value })}
              data-testid="holding-avg-price-input"
              className="w-full bg-transparent border rounded-lg px-3 py-2.5 outline-none" style={{ borderColor: "var(--border)" }} />
          </Field>
        </div>

        {type === "stock" && (
          <Field label="Sector">
            <select value={form.sector} onChange={(e) => setForm({ ...form, sector: e.target.value })}
              data-testid="holding-sector-select"
              className="w-full bg-transparent border rounded-lg px-3 py-2.5 outline-none" style={{ borderColor: "var(--border)" }}>
              {SECTORS.map((s) => <option key={s} value={s} style={{ background: "#121316" }}>{s}</option>)}
            </select>
          </Field>
        )}

        <div className="flex items-center gap-2">
          <input id="sip" type="checkbox" checked={form.is_sip} onChange={(e) => setForm({ ...form, is_sip: e.target.checked })} data-testid="holding-sip-checkbox" />
          <label htmlFor="sip" className="text-sm">This is a SIP</label>
          {form.is_sip && (
            <input type="number" placeholder="Monthly ₹" value={form.sip_amount} onChange={(e) => setForm({ ...form, sip_amount: e.target.value })}
              data-testid="holding-sip-amount-input"
              className="ml-2 w-32 bg-transparent border rounded-lg px-3 py-2 text-sm outline-none" style={{ borderColor: "var(--border)" }} />
          )}
        </div>

        <button type="submit" disabled={submitting} data-testid="holding-submit-btn" className="btn-primary w-full inline-flex items-center justify-center gap-2 py-3">
          <Plus size={16} /> {submitting ? "Adding…" : "Add holding"}
        </button>
      </form>
    </div>
  );
}

const Field = ({ label, children }) => (
  <div>
    <label className="text-sm block mb-1">{label}</label>
    {children}
  </div>
);
