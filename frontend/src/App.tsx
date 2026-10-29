import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AdminPage } from "./features/admin/AdminPage";
import { AppLayout } from "./features/auth/AppLayout";
import { AuthProvider, useAuth } from "./features/auth/AuthContext";
import { LoginPage } from "./features/auth/LoginPage";
import { BaoCaoPage } from "./features/bao-cao/BaoCaoPage";
import { BienXaPage } from "./features/bien-xa/BienXaPage";
import { KhoTinhPage } from "./features/kho-tinh/KhoTinhPage";
import { LoDnmPage } from "./features/lo-dnm/LoDnmPage";
import { LoTinhPage } from "./features/lo-tinh/LoTinhPage";
import { LoXaPage } from "./features/lo-xa/LoXaPage";
import { TraCuuPage } from "./features/tra-cuu/TraCuuPage";

function AppRoutes() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div style={{ padding: 24 }}>Đang tải phiên làm việc...</div>;
  }

  if (!user) {
    return <LoginPage />;
  }

  const defaultRoute =
    user.vai_tro === "ADMIN"
      ? "/admin"
      : user.vai_tro === "TINH"
      ? "/lo-tinh"
      : "/lo-xa";

  return (
    <AppLayout>
      <Routes>
        <Route path="/lo-xa" element={<LoXaPage />} />
        <Route path="/bien-xa" element={<BienXaPage />} />
        <Route path="/lo-tinh" element={<LoTinhPage />} />
        <Route path="/lo-dnm" element={<LoDnmPage />} />
        <Route path="/kho-tinh" element={<KhoTinhPage />} />
        <Route path="/tai-khoan-tinh" element={<AdminPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/tra-cuu" element={<TraCuuPage />} />
        <Route path="/bao-cao" element={<BaoCaoPage />} />
        <Route path="*" element={<Navigate to={defaultRoute} replace />} />
      </Routes>
    </AppLayout>
  );
}

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
