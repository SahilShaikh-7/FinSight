import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Sparkles, TrendingUp, Shield, LineChart, Zap, Brain } from "lucide-react";

const features = [
  { icon: Brain, title: "Money Decision Engine", body: "Not another expense tracker. We tell you why you're overspending and what to do about it." },
  { icon: Sparkles, title: "AI Insights", body: "Claude-powered weekly summaries + rule-based anomaly detection in INR." },
  { icon: LineChart, title: "Investment Tracking", body: "Live NAV from AMFI and free stock prices. SIP-aware portfolio with P&L." },
  { icon: TrendingUp, title: "Financial Health Score", body: "A single 0-100 number that captures your savings rate, stability and spending mix." },
  { icon: Zap, title: "CSV Superpowers", body: "Drop your bank statement. Auto-categorised in seconds — Swiggy, Zomato, Amazon included." },
  { icon: Shield, title: "Built for India", body: "UPI-friendly, INR-native, made for students and first-salary folks." },
];

export default function Landing() {
  return (
    <div className="min-h-screen" style={{ background: "var(--bg-main)" }}>
      {/* Header */}
      <header className="glass-header sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2" data-testid="landing-logo">
            <div className="w-8 h-8 rounded-md grid place-items-center font-bold text-white" style={{ background: "var(--brand)" }}>₹</div>
            <span className="font-display text-lg font-bold tracking-tight">PaisaIQ</span>
          </Link>
          <nav className="flex items-center gap-2">
            <Link to="/login" className="btn-ghost text-sm" data-testid="landing-login-btn">Login</Link>
            <Link to="/register" className="btn-primary text-sm" data-testid="landing-signup-btn">Get started</Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div
          className="absolute inset-0 opacity-30 pointer-events-none"
          style={{
            backgroundImage:
              "url('https://images.unsplash.com/photo-1634744536075-d22f42f88e54?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzV8MHwxfHNlYXJjaHwzfHxhYnN0cmFjdCUyMGRhcmslMjBtb2Rlcm4lMjBmaW5hbmNlJTIwYmFja2dyb3VuZHxlbnwwfHx8fDE3NzY5NzEyNTd8MA&ixlib=rb-4.1.0&q=85')",
            backgroundSize: "cover",
            backgroundPosition: "center",
            maskImage: "linear-gradient(to bottom, rgba(0,0,0,1) 0%, rgba(0,0,0,0) 95%)",
            WebkitMaskImage: "linear-gradient(to bottom, rgba(0,0,0,1) 0%, rgba(0,0,0,0) 95%)",
          }}
        />
        <div className="relative max-w-6xl mx-auto px-6 pt-24 pb-20 md:pt-32 md:pb-28 fade-up">
          <div className="overline mb-4">Personal Finance · AI-native · India</div>
          <h1 className="font-display text-4xl sm:text-5xl lg:text-7xl font-bold tracking-tighter max-w-4xl leading-[1.02]">
            Your money decisions, <span className="text-brand">intelligent</span> from day one.
          </h1>
          <p className="mt-6 text-base md:text-lg text-[color:var(--text-secondary)] max-w-2xl leading-relaxed">
            Upload your bank CSV. Get a Financial Health Score, brutal-honest AI insights, and investment guidance — calibrated for students, freshers, and first-salary Indians. No jargon. Just clarity.
          </p>
          <div className="mt-10 flex flex-wrap items-center gap-3">
            <Link to="/register" data-testid="hero-cta-signup"
              className="btn-primary inline-flex items-center gap-2 text-base px-6 py-3">
              Start free <ArrowRight size={18} />
            </Link>
            <Link to="/login" className="btn-ghost text-base px-6 py-3" data-testid="hero-cta-login">I already have an account</Link>
          </div>
          <div className="mt-16 grid grid-cols-3 gap-6 max-w-xl">
            {[
              { k: "0-100", v: "Health Score" },
              { k: "AI", v: "Insights" },
              { k: "Live", v: "NAV + Stocks" },
            ].map((s) => (
              <div key={s.v} className="card-surface p-4">
                <div className="font-display text-2xl font-bold text-brand">{s.k}</div>
                <div className="text-xs text-[color:var(--text-muted)] mt-1">{s.v}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-6 py-20">
        <div className="overline mb-3">Why PaisaIQ</div>
        <h2 className="font-display text-3xl md:text-5xl font-bold tracking-tight max-w-3xl">
          Built to be <em className="text-brand not-italic">uncomfortably honest</em> about your money.
        </h2>
        <div className="mt-12 grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((f) => {
            const Icon = f.icon;
            return (
              <div key={f.title} className="card-surface p-6">
                <div className="w-10 h-10 rounded-lg grid place-items-center mb-4" style={{ background: "rgba(255,85,0,0.14)", color: "var(--brand)" }}>
                  <Icon size={20} />
                </div>
                <h3 className="font-display text-xl font-semibold mb-2">{f.title}</h3>
                <p className="text-sm text-[color:var(--text-secondary)] leading-relaxed">{f.body}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* Pricing teaser */}
      <section className="max-w-6xl mx-auto px-6 pb-24">
        <div className="card-surface p-10 md:p-14 text-center grain-overlay">
          <div className="overline mb-3">Simple pricing</div>
          <h2 className="font-display text-3xl md:text-5xl font-bold tracking-tight">
            Free forever. Premium starts at <span className="text-brand">₹99</span>.
          </h2>
          <p className="mt-5 text-[color:var(--text-secondary)] max-w-2xl mx-auto">
            Track everything free. Unlock advanced AI insights, investment analytics and predictive forecasts with Premium.
          </p>
          <Link to="/register" data-testid="pricing-cta" className="btn-primary inline-flex items-center gap-2 mt-8 px-6 py-3">
            Create free account <ArrowRight size={18} />
          </Link>
        </div>
      </section>

      <footer className="border-t py-8 text-center text-sm text-[color:var(--text-muted)]" style={{ borderColor: "var(--border)" }}>
        Made in India · © {new Date().getFullYear()} PaisaIQ
      </footer>
    </div>
  );
}
