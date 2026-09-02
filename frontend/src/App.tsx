import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { AlertsListPage } from "./pages/AlertsListPage";
import { AlertDetailPage } from "./pages/AlertDetailPage";
import { PlaybooksPage } from "./pages/PlaybooksPage";
import { IncidentsPage } from "./pages/IncidentsPage";

function protect(children: React.ReactNode) {
  return (
    <ProtectedRoute>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={protect(<DashboardPage />)} />
        <Route path="/alerts" element={protect(<AlertsListPage />)} />
        <Route path="/alerts/:alertId" element={protect(<AlertDetailPage />)} />
        <Route path="/playbooks" element={protect(<PlaybooksPage />)} />
        <Route path="/incidents" element={protect(<IncidentsPage />)} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AuthProvider>
  );
}
