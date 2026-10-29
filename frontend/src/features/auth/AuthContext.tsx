import {
  createContext,
  ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";
import { apiRequest, setCsrfToken } from "../../api/client";

export interface CurrentUser {
  id: number;
  ten_dang_nhap: string;
  vai_tro: "ADMIN" | "TINH" | "XA";
  tinh_ma: string | null;
  xa_ma: string | null;
  bat_buoc_doi_mk: boolean;
  totp_da_bat: boolean;
  can_thiet_lap_2fa?: boolean;
  canh_bao_het_han_mk?: boolean;
  so_ngay_con_lai_mk?: number | null;
}

interface AuthContextValue {
  user: CurrentUser | null;
  loading: boolean;
  refreshUser: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = async () => {
    try {
      const data = await apiRequest<{
        csrf_token?: string;
        user: CurrentUser & { yeu_cau_thiet_lap_2fa?: boolean };
      }>("/api/v1/auth/me");
      if (data.csrf_token) {
        setCsrfToken(data.csrf_token);
      }
      const u = data.user;
      setUser({
        ...u,
        totp_da_bat: !u.yeu_cau_thiet_lap_2fa,
        can_thiet_lap_2fa: !!u.yeu_cau_thiet_lap_2fa,
      });
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refreshUser();
  }, []);

  const logout = async () => {
    try {
      await apiRequest("/api/v1/auth/logout", { method: "POST" });
    } finally {
      setCsrfToken(null);
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, refreshUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth phải được sử dụng bên trong AuthProvider");
  }
  return ctx;
}

