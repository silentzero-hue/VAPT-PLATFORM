import { useEffect, useState } from "react";
import { Route, Routes, Navigate, useLocation, Outlet, Navigate as Nav } from "react-router-dom";
import { setUnauthorizedHandler, setStaleSessionHandler } from "./lib/api";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import LoginPage from "./pages/login/LoginPage";
import TotpPage from "./pages/login/TotpPage";
import AppShell from "./components/layout/AppShell";
import DashboardPage from "./pages/workspaces/DashboardPage";
import EngagementsPage from "./pages/engagements/EngagementsPage";
import EngagementDetailPage from "./pages/engagements/EngagementDetailPage";
import AssetsPage from "./pages/assets/AssetsPage";
import FindingsPage from "./pages/findings/FindingsPage";
import VulnerabilityDetailPage from "./pages/findings/VulnerabilityDetailPage";
import ReportsPage from "./pages/reports/ReportsPage";
import ReportDetailPage from "./pages/reports/ReportDetailPage";
import ReportEditPage from "./pages/reports/ReportEditPage";
import AgentPage from "./pages/agent/AgentPage";
import SettingsPage from "./pages/admin/SettingsPage";
import ThreatIntelPage from "./pages/threat_intel/ThreatIntelPage";
import RetestsPage from "./pages/retests/RetestsPage";
import TokensPage from "./pages/tokens/TokensPage";
import WebhooksPage from "./pages/webhooks/WebhooksPage";
import PortalSharesPage from "./pages/portal/PortalSharesPage";
import LdapPage from "./pages/ldap/LdapPage";
import SbomPage from "./pages/sbom/SbomPage";
import AgentLivePage from "./pages/agent/AgentLivePage";
import PortalLanding from "./pages/reports/PortalLanding";
import NessusServerPage from "./pages/nessus/NessusServerPage";
import MultiScanPage from "./pages/multiscan/MultiScanPage";
import TableViewPage from "./pages/tableview/TableViewPage";
import LegacyImportPage from "./pages/legacy/LegacyImportPage";
import LegacyHelpPage from "./pages/legacy/LegacyHelpPage";

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}

function AppRoutes() {
  const auth = useAuth();
  const [bootChecked, setBootChecked] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setUnauthorizedHandler(() => {
      auth.clear();
      if (!location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    });
    setStaleSessionHandler(() => {
      auth.clear();
      try { localStorage.removeItem("vapt_active_workspace"); } catch {}
      if (!location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!cancelled) await auth.refreshMe();
      if (!cancelled) setBootChecked(true);
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!bootChecked) {
    return (
      <div className="h-screen w-screen flex items-center justify-center text-ink-muted">
        Loading…
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/login/totp" element={<TotpPage />} />
      <Route element={<Protected />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/workspaces" replace />} />
          <Route path="/workspaces" element={<DashboardPage />} />
          <Route path="/workspaces/:wid" element={<DashboardPage />} />
          <Route path="/workspaces/:wid/engagements" element={<EngagementsPage />} />
          <Route
            path="/workspaces/:wid/engagements/:eid"
            element={<EngagementDetailPage />}
          />
          <Route path="/workspaces/:wid/assets" element={<AssetsPage />} />
          <Route path="/workspaces/:wid/findings" element={<FindingsPage />} />
          <Route
            path="/workspaces/:wid/vulnerabilities/:vid"
            element={<VulnerabilityDetailPage />}
          />
          <Route path="/workspaces/:wid/reports" element={<ReportsPage />} />
          <Route
            path="/workspaces/:wid/reports/:rid"
            element={<ReportDetailPage />}
          />
          <Route
            path="/workspaces/:wid/reports/:rid/edit"
            element={<ReportEditPage />}
          />
          <Route path="/workspaces/:wid/agent" element={<AgentPage />} />
          <Route path="/workspaces/:wid/agent/live" element={<AgentLivePage />} />
          <Route path="/workspaces/:wid/settings" element={<SettingsPage />} />
          <Route path="/workspaces/:wid/threat-intel" element={<ThreatIntelPage />} />
          <Route path="/workspaces/:wid/retests" element={<RetestsPage />} />
          <Route path="/workspaces/:wid/tokens" element={<TokensPage />} />
          <Route path="/workspaces/:wid/webhooks" element={<WebhooksPage />} />
          <Route path="/workspaces/:wid/portal" element={<PortalSharesPage />} />
          <Route path="/workspaces/:wid/ldap" element={<LdapPage />} />
          <Route path="/workspaces/:wid/sbom" element={<SbomPage />} />
          <Route path="/workspaces/:wid/nessus" element={<NessusServerPage />} />
          <Route path="/workspaces/:wid/tableview" element={<TableViewPage />} />
          <Route path="/workspaces/:wid/legacy" element={<LegacyImportPage />} />
          <Route path="/workspaces/:wid/legacy/help" element={<LegacyHelpPage />} />
          <Route path="/workspaces/:wid/engagements/:eid/multiscan" element={<MultiScanPage />} />
        </Route>
      </Route>
      <Route path="/portal/:token" element={<PortalLanding />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

function Protected() {
  const auth = useAuth();
  if (!auth.user) return <Nav to="/login" replace />;
  return <Outlet />;
}
