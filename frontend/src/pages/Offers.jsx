import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { CreditCard, PiggyBank, TrendingUp, ExternalLink } from "lucide-react";

const typeIcon = { credit_card: CreditCard, savings_account: PiggyBank, investment: TrendingUp };

export default function Offers() {
  const [recs, setRecs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try { const r = await api.get("/affiliates/recommendations"); setRecs(r.data.recommendations); }
      catch { /* ignore */ }
      finally { setLoading(false); }
    })();
  }, []);

  return (
    <div className="space-y-8 fade-up" data-testid="offers-root">
      <div>
        <div className="overline">Offers</div>
        <h1 className="font-display text-3xl md:text-4xl font-bold tracking-tight mt-1">Curated for your <span className="text-brand">spending pattern</span></h1>
        <p className="text-[color:var(--text-secondary)] mt-2 max-w-xl">Credit cards, savings accounts and investment apps matched to your habits.</p>
      </div>

      {loading ? <div className="text-secondary-muted" data-testid="offers-loading">Loading…</div> :
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {recs.map((r) => {
          const Icon = typeIcon[r.type] || CreditCard;
          return (
            <div key={r.id} className="card-surface p-6 flex flex-col" data-testid={`offer-${r.id}`}>
              <div className="flex items-start justify-between">
                <div className="w-10 h-10 rounded-lg grid place-items-center" style={{ background: "rgba(255,85,0,0.12)", color: "var(--brand)" }}>
                  <Icon size={18} />
                </div>
                <span className="overline">{r.type.replace("_", " ")}</span>
              </div>
              <h3 className="font-display text-lg font-semibold mt-4">{r.name}</h3>
              <p className="text-sm text-[color:var(--text-secondary)] mt-1">{r.tagline}</p>
              <div className="text-xs text-[color:var(--text-muted)] mt-3">{r.bank}</div>
              <div className="mt-4 text-xs p-3 rounded-lg border" style={{ borderColor: "var(--border)", background: "rgba(255,85,0,0.04)" }}>
                <span className="text-brand font-semibold">Why for you:</span> <span className="text-[color:var(--text-secondary)]">{r.match_reason}</span>
              </div>
              <a href={r.link} target="_blank" rel="noreferrer" data-testid={`offer-cta-${r.id}`}
                className="mt-5 btn-primary inline-flex items-center justify-center gap-2 text-sm">
                {r.cta} <ExternalLink size={14} />
              </a>
            </div>
          );
        })}
      </div>}
    </div>
  );
}
