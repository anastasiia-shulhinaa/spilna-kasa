import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "./components/Layout";
import { Spinner } from "./components/ui";
import { useAuth } from "./hooks/useAuth";
import { AddExpensePage } from "./pages/AddExpense";
import { DebtsPage } from "./pages/Debts";
import { HistoryPage } from "./pages/History";
import { LoginPage, RegisterPage } from "./pages/Auth";
import { GroupDetailPage } from "./pages/GroupDetail";
import { GroupsPage } from "./pages/Groups";
import { ProfilePage } from "./pages/Profile";
import { ReceiptPage } from "./pages/ReceiptPage";

function RequireAuth({ children }: { children: ReactNode }) {
  const { token, loading } = useAuth();
  const location = useLocation();
  if (!token) return <Navigate to="/login" replace state={{ from: location }} />;
  if (loading) return <Spinner className="py-32" />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route path="/" element={<GroupsPage />} />
        <Route path="/groups/:id" element={<GroupDetailPage />} />
        <Route path="/groups/:id/expense" element={<AddExpensePage />} />
        <Route path="/groups/:id/receipts/:rid" element={<ReceiptPage />} />
        <Route path="/debts" element={<DebtsPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/profile" element={<ProfilePage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
