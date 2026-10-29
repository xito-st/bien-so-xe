import { FormEvent, useState } from "react";
import { ApiError, apiRequest, setCsrfToken } from "../../api/client";
import { useAuth } from "./AuthContext";

export function LoginPage() {
  const { refreshUser } = useAuth();
  const [tenDangNhap, setTenDangNhap] = useState("");
  const [matKhau, setMatKhau] = useState("");
  const [ma2fa, setMa2fa] = useState("");
  const [can2fa, setCan2fa] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [showForgot, setShowForgot] = useState(false);
  const [forgotUser, setForgotUser] = useState("");
  const [forgotContact, setForgotContact] = useState("");
  const [forgotMsg, setForgotMsg] = useState("");

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const res = await apiRequest<{
        csrf_token?: string;
        yeu_cau_2fa?: boolean;
      }>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({
          ten_dang_nhap: tenDangNhap.trim(),
          mat_khau: matKhau,
          ma_totp: can2fa ? ma2fa.trim() : undefined,
        }),
      });
      if (res.yeu_cau_2fa) {
        setCan2fa(true);
        return;
      }
      if (res.csrf_token) {
        setCsrfToken(res.csrf_token);
      }
      await refreshUser();
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "YEU_CAU_2FA") {
          setCan2fa(true);
          setError("Vui lòng nhập mã xác thực 2 yếu tố (TOTP hoặc mã khôi phục).");
        } else {
          setError(err.message);
        }
      } else {
        setError("Không thể kết nối máy chủ.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleForgotSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setForgotMsg("");
    try {
      const res = await apiRequest<{ message?: string }>(
        "/api/v1/auth/quen-mat-khau",
        {
          method: "POST",
          body: JSON.stringify({
            ten_dang_nhap: forgotUser.trim(),
            lien_he: forgotContact.trim(),
          }),
        }
      );
      setForgotMsg(
        res.message ||
          "Yêu cầu cấp lại mật khẩu đã được ghi nhận vào hàng đợi của Quản trị viên."
      );
    } catch (err) {
      setForgotMsg(
        err instanceof ApiError ? err.message : "Không thể gửi yêu cầu."
      );
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div className="card" style={{ width: 420, padding: 28 }}>
        <h2 style={{ marginTop: 0, marginBottom: 4 }}>
          Hệ thống Quản lý Biển số xe
        </h2>
        <p style={{ color: "var(--color-text-muted)", marginTop: 0 }}>
          Đăng nhập hệ thống quản lý đặt và cấp phát biển số xe
        </p>

        {error && (
          <div
            style={{
              background: "hsl(0, 80%, 95%)",
              color: "var(--color-danger)",
              padding: "8px 12px",
              borderRadius: 4,
              marginBottom: 12,
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} autoComplete="off">
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: "block", fontWeight: 600, marginBottom: 4 }}>
              Tên đăng nhập
            </label>
            <input
              className="input"
              style={{ width: "100%" }}
              value={tenDangNhap}
              onChange={(e) => setTenDangNhap(e.target.value)}
              autoComplete="off"
              required
              autoFocus
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <label style={{ display: "block", fontWeight: 600, marginBottom: 4 }}>
              Mật khẩu
            </label>
            <input
              type="password"
              className="input"
              style={{ width: "100%" }}
              value={matKhau}
              onChange={(e) => setMatKhau(e.target.value)}
              autoComplete="new-password"
              required
            />
          </div>

          {can2fa && (
            <div style={{ marginBottom: 12 }}>
              <label
                style={{ display: "block", fontWeight: 600, marginBottom: 4 }}
              >
                Mã TOTP 6 chữ số hoặc Mã khôi phục 2FA
              </label>
              <input
                className="input"
                style={{ width: "100%" }}
                value={ma2fa}
                onChange={(e) => setMa2fa(e.target.value)}
                required
              />
            </div>
          )}

          <button
            type="submit"
            className="btn"
            style={{ width: "100%", justifyContent: "center", marginTop: 4 }}
            disabled={submitting}
          >
            {submitting ? "Đang xác thực..." : "Đăng nhập"}
          </button>
        </form>

        <div style={{ marginTop: 14, textAlign: "center" }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setShowForgot(true)}
          >
            Quên mật khẩu? Gửi yêu cầu cấp lại
          </button>
        </div>
      </div>

      {showForgot && (
        <div className="modal-backdrop">
          <div className="modal-box">
            <h3 style={{ marginTop: 0 }}>Gửi yêu cầu cấp lại mật khẩu (FR-018)</h3>
            <form onSubmit={handleForgotSubmit}>
              <div style={{ marginBottom: 12 }}>
                <label style={{ display: "block", fontWeight: 600, marginBottom: 4 }}>
                  Tên đăng nhập đơn vị
                </label>
                <input
                  className="input"
                  style={{ width: "100%" }}
                  value={forgotUser}
                  onChange={(e) => setForgotUser(e.target.value)}
                  required
                />
              </div>
              <div style={{ marginBottom: 12 }}>
                <label style={{ display: "block", fontWeight: 600, marginBottom: 4 }}>
                  Thông tin liên hệ xác minh (Họ tên, SĐT trực ban, số công văn)
                </label>
                <input
                  className="input"
                  style={{ width: "100%" }}
                  value={forgotContact}
                  onChange={(e) => setForgotContact(e.target.value)}
                  required
                />
              </div>
              {forgotMsg && (
                <p style={{ color: "var(--color-primary)", fontWeight: 600 }}>
                  {forgotMsg}
                </p>
              )}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    setShowForgot(false);
                    setForgotMsg("");
                  }}
                >
                  Đóng
                </button>
                <button type="submit" className="btn">
                  Gửi yêu cầu
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

