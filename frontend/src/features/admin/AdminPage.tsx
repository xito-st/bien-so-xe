import { FormEvent, useEffect, useState } from "react";
import { ApiError, apiRequest, formatDateTimeVN } from "../../api/client";
import { useAuth } from "../auth/AuthContext";

export function AdminPage() {
  const { user } = useAuth();
  const isAdmin = user?.vai_tro === "ADMIN";
  const [tab, setTab] = useState<"TAI_KHOAN" | "QUEN_MK" | "DANH_MUC" | "AUDIT">(
    "TAI_KHOAN"
  );

  const [accounts, setAccounts] = useState<any[]>([]);
  const [newUsername, setNewUsername] = useState("");
  const [newRole, setNewRole] = useState("XA");
  const [newTinhMa, setNewTinhMa] = useState(user?.tinh_ma || "01");
  const [newXaMa, setNewXaMa] = useState("10105001");
  const [lockReason, setLockReason] = useState("");

  const [forgotList, setForgotList] = useState<any[]>([]);
  const [loaiPts, setLoaiPts] = useState<any[]>([]);
  const [maBienTinhs, setMaBienTinhs] = useState<any[]>([]);
  const [newSeriChu, setNewSeriChu] = useState("");
  const [newTenLp, setNewTenLp] = useState("");
  const [newMaBien, setNewMaBien] = useState("");
  const [newMbtTinh, setNewMbtTinh] = useState("01");

  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const loadAccounts = async () => {
    const res = await apiRequest<{ items: any[] }>("/api/v1/tai-khoan?limit=50");
    setAccounts(res.items || []);
  };

  const loadForgot = async () => {
    if (!isAdmin) return;
    const res = await apiRequest<{ items: any[] }>(
      "/api/v1/admin/yeu-cau-cap-lai-mk"
    );
    setForgotList(res.items || []);
  };

  const loadCatalogs = async () => {
    const [lp, mbt] = await Promise.all([
      apiRequest<{ items: any[] }>("/api/v1/danh-muc/loai-pt?include_inactive=true"),
      apiRequest<{ items: any[] }>(
        "/api/v1/danh-muc/ma-bien-tinh?include_inactive=true"
      ),
    ]);
    setLoaiPts(lp.items || []);
    setMaBienTinhs(mbt.items || []);
  };

  const loadAudit = async () => {
    if (!isAdmin) return;
    const res = await apiRequest<{ items: any[] }>("/api/v1/admin/audit-log");
    setAuditLogs(res.items || []);
  };

  useEffect(() => {
    if (tab === "TAI_KHOAN") void loadAccounts();
    if (tab === "QUEN_MK") void loadForgot();
    if (tab === "DANH_MUC") void loadCatalogs();
    if (tab === "AUDIT") void loadAudit();
  }, [tab]);

  const handleCreateAccount = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setMsg("");
    try {
      await apiRequest("/api/v1/tai-khoan", {
        method: "POST",
        body: JSON.stringify({
          ten_dang_nhap: newUsername.trim(),
          vai_tro: isAdmin ? newRole : "XA",
          tinh_ma: newTinhMa.trim(),
          xa_ma: (isAdmin ? newRole : "XA") === "XA" ? newXaMa.trim() : undefined,
        }),
      });
      setNewUsername("");
      setMsg("Đã tạo tài khoản phụ thành công (FR-003).");
      await loadAccounts();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lỗi tạo tài khoản.");
    }
  };

  const handleLock = async (id: number) => {
    setError("");
    try {
      await apiRequest(`/api/v1/admin/tai-khoan/${id}/khoa`, {
        method: "POST",
        body: JSON.stringify({ ly_do: lockReason || "Khóa theo yêu cầu quản trị" }),
      });
      setMsg("Đã khóa tài khoản và thu hồi mọi phiên đang mở.");
      await loadAccounts();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lỗi khóa tài khoản.");
    }
  };

  const handleUnlock = async (id: number) => {
    await apiRequest(`/api/v1/admin/tai-khoan/${id}/mo-khoa`, { method: "POST" });
    await loadAccounts();
  };

  const handleResetPw = async (id: number) => {
    await apiRequest(`/api/v1/admin/tai-khoan/${id}/dat-lai-mat-khau`, {
      method: "POST",
    });
    setMsg("Đã đặt lại mật khẩu mặc định và buộc đổi lần đầu.");
    await loadAccounts();
  };

  return (
    <div>
      <h2>
        {isAdmin
          ? "Quản trị Hệ thống: Tài khoản, Quên mật khẩu, Danh mục & Audit Log"
          : "Quản lý Tài khoản phụ Xã/Phường trực thuộc (FR-003)"}
      </h2>
      {error && (
        <div className="card" style={{ color: "var(--color-danger)", fontWeight: 600 }}>
          {error}
        </div>
      )}
      {msg && (
        <div className="card" style={{ color: "var(--color-success)", fontWeight: 600 }}>
          {msg}
        </div>
      )}

      {isAdmin && (
        <div className="toolbar">
          <button
            type="button"
            className={`btn ${tab === "TAI_KHOAN" ? "" : "btn-secondary"}`}
            onClick={() => setTab("TAI_KHOAN")}
          >
            Tài khoản
          </button>
          <button
            type="button"
            className={`btn ${tab === "QUEN_MK" ? "" : "btn-secondary"}`}
            onClick={() => setTab("QUEN_MK")}
          >
            Hàng đợi Quên mật khẩu
          </button>
          <button
            type="button"
            className={`btn ${tab === "DANH_MUC" ? "" : "btn-secondary"}`}
            onClick={() => setTab("DANH_MUC")}
          >
            Danh mục (LoaiPT, Nền biển, Mã biển tỉnh)
          </button>
          <button
            type="button"
            className={`btn ${tab === "AUDIT" ? "" : "btn-secondary"}`}
            onClick={() => setTab("AUDIT")}
          >
            Nhật ký Audit Log
          </button>
        </div>
      )}

      {tab === "TAI_KHOAN" && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Tạo tài khoản phụ cho đơn vị (FR-003)</h3>
          <form onSubmit={handleCreateAccount} className="toolbar">
            <input
              className="input"
              placeholder="Tên đăng nhập mới"
              value={newUsername}
              onChange={(e) => setNewUsername(e.target.value)}
              required
            />
            {isAdmin && (
              <select
                className="select"
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
              >
                <option value="XA">Cấp Xã/Phường (XA)</option>
                <option value="TINH">Cấp Tỉnh/Thành (TINH)</option>
              </select>
            )}
            <input
              className="input"
              style={{ width: 90 }}
              placeholder="Mã tỉnh"
              value={newTinhMa}
              onChange={(e) => setNewTinhMa(e.target.value)}
            />
            {(newRole === "XA" || !isAdmin) && (
              <input
                className="input"
                style={{ width: 130 }}
                placeholder="Mã xã/phường"
                value={newXaMa}
                onChange={(e) => setNewXaMa(e.target.value)}
              />
            )}
            <button type="submit" className="btn">
              Tạo tài khoản phụ
            </button>
          </form>

          {isAdmin && (
            <div className="toolbar">
              <input
                className="input"
                placeholder="Lý do khóa thủ công (bắt buộc khi khóa FR-015)"
                value={lockReason}
                onChange={(e) => setLockReason(e.target.value)}
              />
            </div>
          )}

          <table className="data-table">
            <thead>
              <tr>
                <th>Tên đăng nhập</th>
                <th>Vai trò</th>
                <th>Mã tỉnh</th>
                <th>Mã xã</th>
                <th>Trạng thái khóa</th>
                {isAdmin && <th>Thao tác Admin</th>}
              </tr>
            </thead>
            <tbody>
              {accounts.map((tk) => (
                <tr key={tk.id}>
                  <td>
                    <strong>{tk.ten_dang_nhap}</strong>
                  </td>
                  <td>{tk.vai_tro}</td>
                  <td>{tk.tinh_ma || "—"}</td>
                  <td>{tk.xa_ma || "—"}</td>
                  <td>
                    {tk.khoa_thu_cong
                      ? `Khóa thủ công (${tk.ly_do_khoa})`
                      : tk.khoa_den
                      ? `Khóa tạm đến ${formatDateTimeVN(tk.khoa_den)}`
                      : "Hoạt động"}
                  </td>
                  {isAdmin && (
                    <td style={{ display: "flex", gap: 6 }}>
                      {tk.vai_tro !== "ADMIN" && (
                        <>
                          <button
                            type="button"
                            className="btn btn-danger"
                            onClick={() => void handleLock(tk.id)}
                          >
                            Khóa
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => void handleUnlock(tk.id)}
                          >
                            Mở khóa
                          </button>
                          <button
                            type="button"
                            className="btn btn-warning"
                            onClick={() => void handleResetPw(tk.id)}
                          >
                            Đặt lại MK
                          </button>
                        </>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "QUEN_MK" && isAdmin && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Hàng đợi yêu cầu cấp lại mật khẩu (FR-018)</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Tên đăng nhập</th>
                <th>Liên hệ xác minh</th>
                <th>Trạng thái</th>
                <th>Thời điểm</th>
                <th>Xử lý</th>
              </tr>
            </thead>
            <tbody>
              {forgotList.map((yc) => (
                <tr key={yc.id}>
                  <td>{yc.id}</td>
                  <td>
                    <strong>{yc.ten_dang_nhap}</strong>
                  </td>
                  <td>{yc.lien_he}</td>
                  <td>{yc.trang_thai}</td>
                  <td>{formatDateTimeVN(yc.tao_luc)}</td>
                  <td style={{ display: "flex", gap: 6 }}>
                    {yc.trang_thai === "CHO_XU_LY" && (
                      <>
                        <button
                          type="button"
                          className="btn btn-success"
                          onClick={async () => {
                            await apiRequest(
                              `/api/v1/admin/yeu-cau-cap-lai-mk/${yc.id}`,
                              {
                                method: "POST",
                                body: JSON.stringify({ hanh_dong: "DAT_LAI" }),
                              }
                            );
                            await loadForgot();
                          }}
                        >
                          Duyệt đặt lại MK
                        </button>
                        <button
                          type="button"
                          className="btn btn-danger"
                          onClick={async () => {
                            await apiRequest(
                              `/api/v1/admin/yeu-cau-cap-lai-mk/${yc.id}`,
                              {
                                method: "POST",
                                body: JSON.stringify({
                                  hanh_dong: "TU_CHOI",
                                  ly_do_tu_choi: "Chưa đủ thông tin xác minh",
                                }),
                              }
                            );
                            await loadForgot();
                          }}
                        >
                          Từ chối
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "DANH_MUC" && isAdmin && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>
            Quản lý Danh mục LoaiPT & Mã biển tỉnh (FR-037, FR-038)
          </h3>
          <div className="toolbar">
            <input
              className="input"
              placeholder="SeriChữ mới (VD: Z1)"
              value={newSeriChu}
              onChange={(e) => setNewSeriChu(e.target.value)}
            />
            <input
              className="input"
              placeholder="Tên loại phương tiện"
              value={newTenLp}
              onChange={(e) => setNewTenLp(e.target.value)}
            />
            <button
              type="button"
              className="btn"
              onClick={async () => {
                await apiRequest("/api/v1/danh-muc/loai-pt", {
                  method: "POST",
                  body: JSON.stringify({
                    seri_chu: newSeriChu,
                    ten: newTenLp,
                  }),
                });
                setNewSeriChu("");
                setNewTenLp("");
                await loadCatalogs();
              }}
            >
              Thêm LoaiPT
            </button>

            <input
              className="input"
              style={{ width: 90 }}
              placeholder="Mã biển (29)"
              value={newMaBien}
              onChange={(e) => setNewMaBien(e.target.value)}
            />
            <input
              className="input"
              style={{ width: 90 }}
              placeholder="Mã tỉnh (01)"
              value={newMbtTinh}
              onChange={(e) => setNewMbtTinh(e.target.value)}
            />
            <button
              type="button"
              className="btn"
              onClick={async () => {
                await apiRequest("/api/v1/danh-muc/ma-bien-tinh", {
                  method: "POST",
                  body: JSON.stringify({
                    ma_bien: newMaBien,
                    tinh_ma: newMbtTinh,
                  }),
                });
                setNewMaBien("");
                await loadCatalogs();
              }}
            >
              Khai báo Mã biển tỉnh
            </button>
          </div>

          <p>
            Tổng số mục LoaiPT: <strong>{loaiPts.length}</strong> | Tổng số khai báo Mã biển tỉnh:{" "}
            <strong>{maBienTinhs.length}</strong>
          </p>
        </div>
      )}

      {tab === "AUDIT" && isAdmin && (
        <div className="card">
          <div className="toolbar" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0 }}>
              Nhật ký thao tác bất biến Audit Log (FR-021)
            </h3>
            <a href="/api/v1/admin/audit-log/xuat" className="btn btn-secondary">
              Xuất Audit Log (.xlsx)
            </a>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Thời điểm</th>
                <th>Người dùng</th>
                <th>Hành động</th>
                <th>Đối tượng</th>
                <th>Kết quả</th>
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              {auditLogs.map((lg) => (
                <tr key={lg.id}>
                  <td>{formatDateTimeVN(lg.thoi_diem)}</td>
                  <td>{lg.nguoi_dung}</td>
                  <td>
                    <strong>{lg.hanh_dong}</strong>
                  </td>
                  <td>{lg.doi_tuong}</td>
                  <td>{lg.ket_qua}</td>
                  <td>{lg.ip || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

