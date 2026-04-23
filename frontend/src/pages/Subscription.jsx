import React, { useEffect, useState } from "react";
import { api, formatINR } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Check, Sparkles } from "lucide-react";

export default function Subscription() {
  const { user, refreshUser } = useAuth();
  const [plans, setPlans] = useState([]);
  const [loadingPlan, setLoadingPlan] = useState(null);

  useEffect(() => {
    (async () => {
      try { const r = await api.get("/subscription/plans"); setPlans(r.data.plans); }
      catch { toast.error("Failed to load plans"); }
    })();
  }, []);

  const loadRazorpayScript = () => new Promise((resolve) => {
    if (window.Razorpay) return resolve(true);
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => resolve(true);
    s.onerror = () => resolve(false);
    document.body.appendChild(s);
  });

  const handleSubscribe = async (planId) => {
    setLoadingPlan(planId);
    try {
      const ok = await loadRazorpayScript();
      if (!ok) { toast.error("Could not load Razorpay"); return; }
      const r = await api.post("/subscription/create-order", { plan: planId });
      const { order_id, amount, currency, key_id } = r.data;

      const options = {
        key: key_id,
        amount,
        currency,
        name: "PaisaIQ",
        description: `${planId === "basic" ? "Basic" : "Pro"} Premium`,
        order_id,
        prefill: { name: user?.name, email: user?.email },
        theme: { color: "#FF5500" },
        handler: async (resp) => {
          try {
            await api.post("/subscription/verify", resp);
            toast.success("Premium activated!");
            await refreshUser();
          } catch (e) { toast.error("Verification failed"); }
        },
        modal: { ondismiss: () => { setLoadingPlan(null); } },
      };
      const rzp = new window.Razorpay(options);
      rzp.open();
    } catch (err) {
      const msg = err?.response?.data?.detail || "Payment setup failed";
      toast.error(msg);
      if (String(msg).includes("not configured")) {
        toast.message("Add your Razorpay keys to backend/.env to enable payments.");
      }
    } finally {
      setLoadingPlan(null);
    }
  };

  return (
    <div className="space-y-8 fade-up" data-testid="subscription-root">
      <div>
        <div className="overline">Pricing</div>
        <h1 className="font-display text-3xl md:text-5xl font-bold tracking-tight mt-1">Upgrade your <span className="text-brand">money IQ</span></h1>
        <p className="text-[color:var(--text-secondary)] mt-2 max-w-xl">Current plan: <span className="font-semibold capitalize">{user?.plan}</span>. Pay via UPI / cards / netbanking — secured by Razorpay.</p>
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        <PlanCard
          name="Free"
          price="₹0"
          features={["Expense tracking", "Smart categorization", "Basic insights", "Financial Health Score"]}
          cta={user?.plan === "free" ? "Current plan" : "Downgrade"}
          disabled testid="plan-free"
        />
        {plans.map((p) => (
          <PlanCard
            key={p.id}
            name={p.name}
            price={formatINR(p.amount_inr)}
            period="/month"
            features={p.features}
            cta={user?.plan === p.id ? "Current plan" : loadingPlan === p.id ? "Processing…" : "Subscribe"}
            onClick={() => handleSubscribe(p.id)}
            disabled={user?.plan === p.id || !!loadingPlan}
            highlight={p.id === "pro"}
            testid={`plan-${p.id}`}
          />
        ))}
      </div>

      <div className="card-surface p-6 grain-overlay" data-testid="trust-note">
        <div className="flex items-start gap-3">
          <Sparkles size={18} className="text-brand mt-1 shrink-0" />
          <div className="text-sm text-[color:var(--text-secondary)]">
            Your data is never sold. Cancel anytime. GST-compliant invoices. For business or student discounts, contact support.
          </div>
        </div>
      </div>
    </div>
  );
}

const PlanCard = ({ name, price, period, features, cta, onClick, disabled, highlight, testid }) => (
  <div className={`card-surface p-8 relative ${highlight ? "border-[color:var(--brand)]" : ""}`} data-testid={testid}
    style={highlight ? { borderColor: "var(--brand)" } : {}}>
    {highlight && <div className="absolute -top-3 left-6 overline bg-[color:var(--brand)] text-white px-2 py-1 rounded-md">Most popular</div>}
    <h3 className="font-display text-xl font-semibold">{name}</h3>
    <div className="mt-4 flex items-baseline gap-1">
      <span className="font-display text-4xl font-bold">{price}</span>
      {period && <span className="text-[color:var(--text-secondary)]">{period}</span>}
    </div>
    <ul className="mt-6 space-y-3">
      {features.map((f) => (
        <li key={f} className="flex items-start gap-2 text-sm">
          <Check size={16} className="text-green-400 mt-0.5 shrink-0" /> <span className="text-[color:var(--text-secondary)]">{f}</span>
        </li>
      ))}
    </ul>
    <button onClick={onClick} disabled={disabled} data-testid={`${testid}-cta`}
      className={`mt-8 w-full py-3 rounded-lg font-semibold transition-colors ${highlight ? "btn-primary" : "btn-ghost"} disabled:opacity-40 disabled:cursor-not-allowed`}>
      {cta}
    </button>
  </div>
);
