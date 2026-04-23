import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "../lib/api";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("fin_user");
    return raw ? JSON.parse(raw) : null;
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("fin_token");
    if (!token) { setLoading(false); return; }
    api.get("/auth/me")
      .then((r) => { setUser(r.data); localStorage.setItem("fin_user", JSON.stringify(r.data)); })
      .catch(() => { localStorage.removeItem("fin_token"); localStorage.removeItem("fin_user"); setUser(null); })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const r = await api.post("/auth/login", { email, password });
    localStorage.setItem("fin_token", r.data.token);
    localStorage.setItem("fin_user", JSON.stringify(r.data.user));
    setUser(r.data.user);
    return r.data.user;
  };

  const register = async (email, password, name) => {
    await api.post("/auth/register", { email, password, name });
    return await login(email, password);
  };

  const logout = () => {
    localStorage.removeItem("fin_token");
    localStorage.removeItem("fin_user");
    setUser(null);
  };

  const refreshUser = async () => {
    const r = await api.get("/auth/me");
    setUser(r.data);
    localStorage.setItem("fin_user", JSON.stringify(r.data));
    return r.data;
  };

  return <AuthContext.Provider value={{ user, loading, login, register, logout, refreshUser }}>{children}</AuthContext.Provider>;
};

export const useAuth = () => useContext(AuthContext);
