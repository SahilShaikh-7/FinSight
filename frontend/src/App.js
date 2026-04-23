import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "@/context/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import DashboardLayout from "@/components/DashboardLayout";

import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import Dashboard from "@/pages/Dashboard";
import Expenses from "@/pages/Expenses";
import Insights from "@/pages/Insights";
import Portfolio from "@/pages/Portfolio";
import Subscription from "@/pages/Subscription";
import Offers from "@/pages/Offers";
import Settings from "@/pages/Settings";

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Toaster theme="dark" position="top-right" richColors />
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/app" element={
              <ProtectedRoute><DashboardLayout /></ProtectedRoute>
            }>
              <Route index element={<Navigate to="/app/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="expenses" element={<Expenses />} />
              <Route path="insights" element={<Insights />} />
              <Route path="portfolio" element={<Portfolio />} />
              <Route path="subscription" element={<Subscription />} />
              <Route path="offers" element={<Offers />} />
              <Route path="settings" element={<Settings />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
