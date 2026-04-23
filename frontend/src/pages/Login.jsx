import React, { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { ArrowRight } from "lucide-react";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const loc = useLocation();
  const redirect = loc.state?.from?.pathname || "/app/dashboard";

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      toast.success("Welcome back!");
      navigate(redirect, { replace: true });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Login failed");
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen grid md:grid-cols-2" style={{ background: "var(--bg-main)" }}>
      <div className="hidden md:flex flex-col justify-between p-12 relative overflow-hidden border-r" style={{ borderColor: "var(--border)" }}>
        <Link to="/" className="flex items-center gap-2" data-testid="login-brand">
          <div className="w-9 h-9 rounded-md grid place-items-center font-bold text-white" style={{ background: "var(--brand)" }}>₹</div>
          <span className="font-display text-xl font-bold">FinSight</span>
        </Link>
        <div className="relative z-10">
          <div className="overline mb-3">Welcome back</div>
          <h2 className="font-display text-4xl lg:text-5xl font-bold tracking-tight leading-tight">
            Your money, <br /><span className="text-brand">decoded.</span>
          </h2>
          <p className="mt-4 text-[color:var(--text-secondary)] max-w-sm">
            Sign in to see updated insights, your Financial Health Score, and fresh portfolio NAVs.
          </p>
        </div>
        <div className="text-sm text-[color:var(--text-muted)]">Your data is encrypted and private.</div>
      </div>

      <div className="flex items-center justify-center p-6 md:p-12">
        <form onSubmit={onSubmit} className="w-full max-w-sm card-surface p-8" data-testid="login-form">
          <h1 className="font-display text-2xl font-bold mb-1">Login</h1>
          <p className="text-sm text-[color:var(--text-secondary)] mb-6">Enter your credentials to continue.</p>
          <label className="text-sm font-medium">Email</label>
          <input
            type="email" required autoComplete="email" data-testid="login-email-input"
            value={email} onChange={(e) => setEmail(e.target.value)}
            className="mt-1 mb-4 w-full bg-transparent border rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-[color:var(--brand)]"
            style={{ borderColor: "var(--border)" }}
          />
          <label className="text-sm font-medium">Password</label>
          <input
            type="password" required autoComplete="current-password" data-testid="login-password-input"
            value={password} onChange={(e) => setPassword(e.target.value)}
            className="mt-1 mb-6 w-full bg-transparent border rounded-lg px-3 py-2.5 outline-none focus:ring-2 focus:ring-[color:var(--brand)]"
            style={{ borderColor: "var(--border)" }}
          />
          <button type="submit" disabled={loading} data-testid="login-submit-btn"
            className="btn-primary w-full inline-flex items-center justify-center gap-2 py-3">
            {loading ? "Signing in…" : <>Sign in <ArrowRight size={16} /></>}
          </button>
          <div className="mt-6 text-sm text-[color:var(--text-secondary)] text-center">
            New here? <Link to="/register" className="text-brand font-semibold" data-testid="login-to-register">Create an account</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
