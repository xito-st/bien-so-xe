import { FormEvent, useEffect, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ApiError, apiRequest, formatDateTimeVN } from "../../api/client";
import { ConfirmModal, StatusBadge } from "../../components/ConfirmModal";

interface LoItem {
  id: number;
  ma_lo: string;
  so_cong_van: string;
  loai: string;
  trang_thai: string;
  so_bien?: number;
  tao_luc?: string;
}

interface BienItem {
  id: number;
  stt: number;
  ma_lo: string;
  don_vi: string;
  loai_pt: string;
  mau_sac: string;
  bien_so_day_du: string;
  ngoai_tinh: boolean;
  loi_ly_do?: string | null;
}

export function LoXaPage() {
  const [los, setLos] = useState<LoItem[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedLo, setSelectedLo] = useState<LoItem | null>(null);
  const [plates, setPlates] = useState<BienItem[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  const [newSoCv, setNewSoCv] = useState("");
  const [bienInput, setBienInput] = useState("");
  const [mauSac, setMauSac] = useState("TRẮNG");
  const [inlinePreview, setInlinePreview] = useState<any>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [confirmGuiOpen, setConfirmGuiOpen] = useState(false);
  const [confirmReorderOpen, setConfirmReorderOpen] = useState(false);

  const parentRef = useRef<HTMLDivElement>(null);
  const rowVirtualizer = useVirtualizer({
    count: plates.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 38,
    overscan: 10,
  });

  const loadLos = async () => {
    const qs = statusFilter
      ? `?loai=XA&trang_thai=${encodeURIComponent(statusFilter)}`
      : "?loai=XA";
    const res = await apiRequest<{ items: LoItem[] }>(`/api/v1/lo${qs}`);
    setLos(res.items || []);
  };

  const loadPlates = async (loId: number) => {
    const res = await apiRequest<{ items: BienItem[] }>(
      `/api/v1/lo/${loId}/bien`
    );
    setPlates(res.items || []);
  };

  useEffect(() => {
    void loadLos();
  }, [statusFilter]);

  useEffect(() => {
    if (!bienInput.trim() || !selectedLo) {
      setInlinePreview(null);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await apiRequest("/api/v1/bien/kiem-tra", {
          method: "POST",
          body: JSON.stringify({
            lo_id: selectedLo.id,
            bien_so: bienInput,
            mau_sac: mauSac,
          }),
        });
        setInlinePreview(res);
      } catch {
        setInlinePreview(null);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [bienInput, mauSac, selectedLo]);

  const handleCreateLo = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const created = await apiRequest<LoItem>("/api/v1/lo", {
        method: "POST",
        body: JSON.stringify({ loai: "XA", so_cong_van: newSoCv.trim() }),
      });
      setNewSoCv("");
      await loadLos();
      setSelectedLo(created);
      await loadPlates(created.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lỗi tạo lô.");
    }
  };

  const handleAddPlate = async (datLaiXacNhan = false) => {
    if (!selectedLo) return;
    setError("");
    setMessage("");
    try {
      await apiRequest(`/api/v1/lo/${selectedLo.id}/bien`, {
        method: "POST",
        body: JSON.stringify({
          bien_so: bienInput.trim(),
          mau_sac: mauSac,
          dat_lai_xac_nhan: datLaiXacNhan,
        }),
      });
      setBienInput("");
      setConfirmReorderOpen(false);
      await loadPlates(selectedLo.id);
      await loadLos();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && !datLaiXacNhan) {
        setConfirmReorderOpen(true);
      } else {
        setError(err instanceof ApiError ? err.message : "Lỗi thêm biển.");
      }
    }
  };

  const handleGuiLo = async () => {
    if (!selectedLo) return;
    setConfirmGuiOpen(false);
    setError("");
    try {
      const updated = await apiRequest<LoItem>(
        `/api/v1/lo/${selectedLo.id}/gui`,
        {
          method: "POST",
          body: JSON.stringify({ xac_nhan: true }),
        }
      );
      setSelectedLo(updated);
      setMessage(`Đã gửi lô ${updated.ma_lo} (${updated.trang_thai}).`);
      await loadLos();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lỗi gửi lô.");
    }
  };

  const handleRetrySync = async () => {
    if (!selectedLo) return;
    try {
      const updated = await apiRequest<LoItem>(
        `/api/v1/lo/${selectedLo.id}/dong-bo-lai`,
        { method: "POST" }
      );
      setSelectedLo(updated);
      await loadLos();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lỗi đồng bộ lại.");
    }
  };

  const handleImportXlsx = async (file: File) => {
    if (!selectedLo) return;
    setError("");
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await apiRequest<any>(
        `/api/v1/lo/${selectedLo.id}/bien/import`,
        {
          method: "POST",
          body: fd,
        }
      );
      setMessage(
        `Đã import ${res.so_luong_them ?? 0} biển số thành công.`
      );
      await loadPlates(selectedLo.id);
      await loadLos();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lỗi import Excel.");
    }
  };

  const openHistory = async (loId: number) => {
    const res = await apiRequest<{ items: any[] }>(
      `/api/v1/lo/${loId}/lich-su`
    );
    setHistory(res.items || []);
    setShowHistory(true);
  };

  return (
    <div>
      <h2>Quản lý Lô biển số Xã/Phường (FR-040..048)</h2>
      {error && (
        <div className="card" style={{ color: "var(--color-danger)", fontWeight: 600 }}>
          {error}
        </div>
      )}
      {message && (
        <div className="card" style={{ color: "var(--color-success)", fontWeight: 600 }}>
          {message}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "380px 1fr", gap: 16 }}>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Danh sách Lô của Xã</h3>
          <form onSubmit={handleCreateLo} className="toolbar">
            <input
              className="input"
              placeholder="Số công văn (VD: 01/CV)"
              value={newSoCv}
              onChange={(e) => setNewSoCv(e.target.value)}
              required
            />
            <button type="submit" className="btn">
              Tạo lô mới
            </button>
          </form>

          <div className="toolbar">
            <select
              className="select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">Tất cả trạng thái</option>
              <option value="Khởi tạo">Khởi tạo</option>
              <option value="Đã gửi">Đã gửi</option>
              <option value="Chờ phê duyệt">Chờ phê duyệt</option>
              <option value="Chấp nhận">Chấp nhận</option>
              <option value="Từ chối">Từ chối</option>
              <option value="Cho phép điều chỉnh">Cho phép điều chỉnh</option>
              <option value="Đặt thành công">Đặt thành công</option>
              <option value="Đã nhận">Đã nhận</option>
            </select>
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th>Mã lô</th>
                <th>Trạng thái</th>
                <th>Số biển</th>
              </tr>
            </thead>
            <tbody>
              {los.map((l) => (
                <tr
                  key={l.id}
                  style={{
                    cursor: "pointer",
                    background:
                      selectedLo?.id === l.id ? "hsl(215, 70%, 95%)" : undefined,
                  }}
                  onClick={() => {
                    setSelectedLo(l);
                    void loadPlates(l.id);
                  }}
                >
                  <td>
                    <strong>{l.ma_lo}</strong>
                  </td>
                  <td>
                    <StatusBadge status={l.trang_thai} />
                  </td>
                  <td>{l.so_bien ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          {!selectedLo ? (
            <p>Chọn một lô bên trái để xem và quản lý danh sách biển số.</p>
          ) : (
            <>
              <div className="toolbar" style={{ justifyContent: "space-between" }}>
                <div>
                  <h3 style={{ margin: 0 }}>
                    Mã lô: {selectedLo.ma_lo} —{" "}
                    <StatusBadge status={selectedLo.trang_thai} />
                  </h3>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <a
                    href="/api/v1/import/file-mau.xlsx"
                    className="btn btn-secondary"
                  >
                    Tải file mẫu (.xlsx)
                  </a>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => void openHistory(selectedLo.id)}
                  >
                    Lịch sử trạng thái
                  </button>
                  {selectedLo.trang_thai === "Đã gửi" && (
                    <button
                      type="button"
                      className="btn btn-warning"
                      onClick={() => void handleRetrySync()}
                    >
                      Đồng bộ lại
                    </button>
                  )}
                  {["Khởi tạo", "Từ chối", "Cho phép điều chỉnh"].includes(
                    selectedLo.trang_thai
                  ) && (
                    <button
                      type="button"
                      className="btn btn-success"
                      onClick={() => setConfirmGuiOpen(true)}
                    >
                      Gửi lô lên Tỉnh
                    </button>
                  )}
                </div>
              </div>

              {["Khởi tạo", "Từ chối", "Cho phép điều chỉnh"].includes(
                selectedLo.trang_thai
              ) && (
                <div className="card" style={{ background: "#f8fafc" }}>
                  <div className="toolbar">
                    <input
                      className="input"
                      placeholder="Nhập biển số (VD: 29A-123.45)"
                      value={bienInput}
                      onChange={(e) => setBienInput(e.target.value)}
                    />
                    <select
                      className="select"
                      value={mauSac}
                      onChange={(e) => setMauSac(e.target.value)}
                    >
                      <option value="TRẮNG">Nền TRẮNG</option>
                      <option value="VÀNG">Nền VÀNG</option>
                      <option value="XANH">Nền XANH</option>
                    </select>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => void handleAddPlate(false)}
                    >
                      Thêm biển số
                    </button>
                    <label className="btn btn-secondary">
                      Import Excel (.xlsx)
                      <input
                        type="file"
                        accept=".xlsx"
                        style={{ display: "none" }}
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          if (f) void handleImportXlsx(f);
                        }}
                      />
                    </label>
                  </div>
                  {inlinePreview && (
                    <div style={{ fontSize: 13 }}>
                      {inlinePreview.hop_le ? (
                        <span>
                          Chuẩn hóa:{" "}
                          <strong>{inlinePreview.bien_so_day_du}</strong> | Loại PT:{" "}
                          <strong>{inlinePreview.loai_pt}</strong> | Màu sắc:{" "}
                          <strong>{inlinePreview.mau_sac}</strong>
                          {inlinePreview.ngoai_tinh && (
                            <span
                              style={{
                                color: "var(--color-warning)",
                                marginLeft: 8,
                                fontWeight: 600,
                              }}
                            >
                              (Cảnh báo: Biển ngoại tỉnh FR-038)
                            </span>
                          )}
                        </span>
                      ) : (
                        <span style={{ color: "var(--color-danger)" }}>
                          {inlinePreview.loi}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Bảng 6 cột ảo hóa cho tới 5.000 dòng (FR-041) */}
              <div
                ref={parentRef}
                style={{
                  height: 440,
                  overflow: "auto",
                  border: "1px solid var(--color-border)",
                }}
              >
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>STT</th>
                      <th>MÃ LÔ</th>
                      <th>ĐƠN VỊ</th>
                      <th>LOẠI PHƯƠNG TIỆN</th>
                      <th>MÀU SẮC</th>
                      <th>BIỂN SỐ ĐẦY ĐỦ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                      const p = plates[virtualRow.index];
                      return (
                        <tr key={p.id}>
                          <td>{p.stt}</td>
                          <td>{p.ma_lo}</td>
                          <td>{p.don_vi}</td>
                          <td>{p.loai_pt}</td>
                          <td>{p.mau_sac}</td>
                          <td>
                            <strong>{p.bien_so_day_du}</strong>
                            {p.ngoai_tinh && (
                              <span
                                className="badge badge-warning"
                                style={{ marginLeft: 6 }}
                              >
                                Ngoại tỉnh
                              </span>
                            )}
                            {p.loi_ly_do && (
                              <span
                                className="badge badge-danger"
                                style={{ marginLeft: 6 }}
                              >
                                Lỗi: {p.loi_ly_do}
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>

      <ConfirmModal
        open={confirmGuiOpen}
        title="Xác nhận Gửi lô biển số lên Tỉnh/Thành (FR-044, FR-091)"
        onConfirm={() => void handleGuiLo()}
        onCancel={() => setConfirmGuiOpen(false)}
      >
        <p>
          Sau khi gửi, Số công văn và Mã lô ({selectedLo?.ma_lo}) sẽ bất biến và lô được đồng bộ lên Tỉnh/Thành để chờ phê duyệt. Bạn có chắc chắn muốn gửi?
        </p>
      </ConfirmModal>

      <ConfirmModal
        open={confirmReorderOpen}
        title="Xác nhận đặt lại biển số đã trả / thu hồi về xã (FR-036 mục d)"
        onConfirm={() => void handleAddPlate(true)}
        onCancel={() => setConfirmReorderOpen(false)}
      >
        <p>
          Biển số này từng ở trạng thái Đã trả hoặc Thu hồi về xã trong tỉnh. Bạn có xác nhận muốn đặt lại biển số này không?
        </p>
      </ConfirmModal>

      {showHistory && (
        <div className="modal-backdrop">
          <div className="modal-box">
            <h3 style={{ marginTop: 0 }}>Lịch sử chuyển trạng thái lô (FR-048)</h3>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Thời điểm</th>
                  <th>Từ</th>
                  <th>Đến</th>
                  <th>Người thực hiện</th>
                  <th>Lý do / Ghi chú</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h, idx) => (
                  <tr key={idx}>
                    <td>{formatDateTimeVN(h.luc)}</td>
                    <td>{h.tu || "—"}</td>
                    <td>{h.den}</td>
                    <td>{h.nguoi}</td>
                    <td>{h.ly_do || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ marginTop: 12, textAlign: "right" }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowHistory(false)}
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
