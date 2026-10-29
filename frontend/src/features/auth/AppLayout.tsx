import { FormEvent, ReactNode, useState } from "react";
import { NavLink } from "react-router-dom";
import { ApiError, apiRequest } from "../../api/client";
import { useAuth } from "./AuthContext";

export function ChangePasswordModal({
  forced,
  onClose,
}: {
  forced: boolean;
  onClose?: () => void;
}) {
  const { refreshUser, logout } = useAuth();
  const [matKhauHienTai, setMatKhauHienTai] = useState("");
  const [matKhauMoi, setMatKhauMoi] = useState("");
  const [xacNhanMatKhauMoi, setXacNhanMatKhauMoi] = useState("");
  const [error, setError] = useState("");
  const [step4Success, setStep4Success] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await apiRequest("/api/v1/auth/doi-mat-khau", {
        method: "POST",
        body: JSON.stringify({
          mat_khau_hien_tai: matKhauHienTai,
          mat_khau_moi: matKhauMoi,
          xac_nhan_mat_khau_moi: xacNhanMatKhauMoi,
        }),
      });
      setStep4Success(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Đổi mật khẩu thất bại.");
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-box">
        <h3 style={{ marginTop: 0 }}>
          {forced
            ? "Bắt buộc đổi mật khẩu trước khi sử dụng (FR-012)"
            : "Đổi mật khẩu tài khoản (4 bước FR-012)"}
        </h3>
        {step4Success ? (
          <div>
            <p style={{ color: "var(--color-success)", fontWeight: 600 }}>
              Bước 4/4: Đổi mật khẩu thành công! Hệ thống sẽ chuyển về trang chức năng.
            </p>
            <button
              type="button"
              className="btn"
              onClick={async () => {
                await refreshUser();
                onClose?.();
              }}
            >
              Tiếp tục vào hệ thống
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            {error && (
              <p style={{ color: "var(--color-danger)", fontWeight: 600 }}>
                {error}
              </p>
            )}
            <div style={{ marginBottom: 10 }}>
              <label style={{ display: "block", fontWeight: 600 }}>
                Bước 1: Nhập mật khẩu hiện tại
              </label>
              <input
                type="password"
                className="input"
                style={{ width: "100%" }}
                value={matKhauHienTai}
                onChange={(e) => setMatKhauHienTai(e.target.value)}
                required
              />
            </div>
            <div style={{ marginBottom: 10 }}>
              <label style={{ display: "block", fontWeight: 600 }}>
                Bước 2: Nhập mật khẩu mới (≥ 10 ký tự, đủ chữ hoa, chữ thường, chữ số, ký tự đặc biệt)
              </label>
              <input
                type="password"
                className="input"
                style={{ width: "100%" }}
                value={matKhauMoi}
                onChange={(e) => setMatKhauMoi(e.target.value)}
                required
              />
            </div>
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: "block", fontWeight: 600 }}>
                Bước 3: Xác nhận mật khẩu mới
              </label>
              <input
                type="password"
                className="input"
                style={{ width: "100%" }}
                value={xacNhanMatKhauMoi}
                onChange={(e) => setXacNhanMatKhauMoi(e.target.value)}
                required
              />
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              {forced ? (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => void logout()}
                >
                  Đăng xuất
                </button>
              ) : (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={onClose}
                >
                  Hủy
                </button>
              )}
              <button type="submit" className="btn">
                Xác nhận đổi mật khẩu
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

export function TotpSetupModal() {
  const { refreshUser, logout } = useAuth();
  const [secret, setSecret] = useState("");
  const [uri, setUri] = useState("");
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [error, setError] = useState("");

  const startSetup = async () => {
    setError("");
    try {
      const res = await apiRequest<{ secret: string; provisioning_uri: string }>(
        "/api/v1/auth/totp/thiet-lap",
        { method: "POST" }
      );
      setSecret(res.secret);
      setUri(res.provisioning_uri);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lỗi khởi tạo 2FA.");
    }
  };

  const confirmSetup = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const res = await apiRequest<{ ma_khoi_phuc: string[] }>(
        "/api/v1/auth/totp/xac-nhan",
        {
          method: "POST",
          body: JSON.stringify({ ma_totp: code.trim() }),
        }
      );
      setRecoveryCodes(res.ma_khoi_phuc || []);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Mã TOTP không hợp lệ.");
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-box">
        <h3 style={{ marginTop: 0 }}>
          Thiết lập Xác thực 2 yếu tố (TOTP) cho Admin (FR-019)
        </h3>
        {recoveryCodes.length > 0 ? (
          <div>
            <p style={{ color: "var(--color-success)", fontWeight: 600 }}>
              Đã kích hoạt 2FA thành công! Lưu ngay 10 mã khôi phục dùng một lần dưới đây:
            </p>
            <pre
              style={{
                background: "#f1f5f9",
                padding: 12,
                borderRadius: 6,
                fontWeight: 600,
              }}
            >
              {recoveryCodes.join("\n")}
            </pre>
            <button
              type="button"
              className="btn"
              onClick={() => void refreshUser()}
            >
              Tôi đã lưu mã khôi phục — Tiếp tục
            </button>
          </div>
        ) : !secret ? (
          <div>
            <p>
              Tài khoản Admin bắt buộc kích hoạt xác thực 2 yếu tố (TOTP) trước khi quản trị hệ thống.
            </p>
            {error && <p style={{ color: "var(--color-danger)" }}>{error}</p>}
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" className="btn" onClick={() => void startSetup()}>
                Tạo khóa TOTP
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => void logout()}
              >
                Đăng xuất
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={confirmSetup}>
            <p>
              Nhập khóa bí mật sau vào ứng dụng xác thực (Google Authenticator / Microsoft Authenticator):
            </p>
            <code
              style={{
                display: "block",
                padding: 8,
                background: "#f1f5f9",
                marginBottom: 8,
                fontWeight: 700,
              }}
            >
              {secret}
            </code>
            <small style={{ display: "block", wordBreak: "break-all", marginBottom: 12 }}>
              URI: {uri}
            </small>
            {error && <p style={{ color: "var(--color-danger)" }}>{error}</p>}
            <input
              className="input"
              style={{ width: "100%", marginBottom: 12 }}
              placeholder="Nhập mã 6 chữ số từ ứng dụng"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              required
            />
            <button type="submit" className="btn">
              Xác nhận kích hoạt 2FA
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

export function AppLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const [showChangePw, setShowChangePw] = useState(false);

  if (!user) return null;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h2>QUẢN LÝ BIỂN SỐ XE (34 TỈNH/THÀNH)</h2>
        {user.vai_tro === "XA" && (
          <>
            <NavLink to="/lo-xa" className="nav-link">
              Lô biển số của Xã/Phường
            </NavLink>
            <NavLink to="/bien-xa" className="nav-link">
              Biển đã nhận & Trả/Thu hồi/Hủy
            </NavLink>
          </>
        )}
        {user.vai_tro === "TINH" && (
          <>
            <NavLink to="/lo-tinh" className="nav-link">
              Duyệt lô Xã & Quản lý Lô Tỉnh
            </NavLink>
            <NavLink to="/lo-dnm" className="nav-link">
              Lô đặt nhà máy
            </NavLink>
            <NavLink to="/kho-tinh" className="nav-link">
              Kho Tỉnh & Bàn giao Xã
            </NavLink>
            <NavLink to="/tai-khoan-tinh" className="nav-link">
              Tài khoản Xã trực thuộc
            </NavLink>
          </>
        )}
        {user.vai_tro === "ADMIN" && (
          <>
            <NavLink to="/admin" className="nav-link">
              Quản trị Tài khoản, Danh mục & Audit
            </NavLink>
          </>
        )}
        <NavLink to="/tra-cuu" className="nav-link">
          Tra cứu biển số
        </NavLink>
        <NavLink to="/bao-cao" className="nav-link">
          Báo cáo thống kê (R1–R5)
        </NavLink>
      </aside>

      <div className="main-area">
        {user.canh_bao_het_han_mk && (
          <div className="banner-warning">
            Cảnh báo: Mật khẩu của bạn sẽ hết hạn sau{" "}
            {user.so_ngay_con_lai_mk ?? 7} ngày (chu kỳ 90 ngày theo FR-013). Vui lòng đổi mật khẩu sớm.
          </div>
        )}
        <header className="topbar">
          <div>
            <strong>Tài khoản:</strong> {user.ten_dang_nhap} |{" "}
            <strong>Vai trò:</strong> {user.vai_tro}
            {user.tinh_ma ? ` | Mã tỉnh: ${user.tinh_ma}` : ""}
            {user.xa_ma ? ` | Mã xã: ${user.xa_ma}` : ""}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setShowChangePw(true)}
            >
              Đổi mật khẩu
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => void logout()}
            >
              Đăng xuất
            </button>
          </div>
        </header>

        <main className="content-body">{children}</main>
      </div>

      {user.bat_buoc_doi_mk && <ChangePasswordModal forced={true} />}
      {!user.bat_buoc_doi_mk &&
        user.vai_tro === "ADMIN" &&
        !user.totp_da_bat && <TotpSetupModal />}
      {showChangePw && (
        <ChangePasswordModal
          forced={false}
          onClose={() => setShowChangePw(false)}
        />
      )}
    </div>
  );
}
