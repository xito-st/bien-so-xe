import { FormEvent, useEffect, useState } from "react";
import { ApiError, apiRequest } from "../../api/client";
import { ConfirmModal, StatusBadge } from "../../components/ConfirmModal";

export function LoTinhPage() {
  const [tab, setTab] = useState<"LO_XA" | "LO_TINH">("LO_XA");
  const [los, setLos] = useState<any[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [selectedLo, setSelectedLo] = useState<any | null>(null);
  const [plates, setPlates] = useState<any[]>([]);

  const [newSoCv, setNewSoCv] = useState("");
  const [newBien, setNewBien] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [errorPlatesMap, setErrorPlatesMap] = useState<Record<number, string>>(
    {}
  );

  const [confirmBulkOpen, setConfirmBulkOpen] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const loadLos = async () => {
    const loai = tab === "LO_XA" ? "XA" : "TINH";
    const res = await apiRequest<{ items: any[] }>(`/api/v1/lo?loai=${loai}`);
    setLos(res.items || []);
  };

  const loadPlates = async (loId: number) => {
    const res = await apiRequest<{ items: any[] }>(`/api/v1/lo/${loId}/bien`);
    setPlates(res.items || []);
  };

  useEffect(() => {
    setSelectedLo(null);
    setPlates([]);
    setSelectedIds([]);
    void loadLos();
  }, [tab]);

  const handleBulkApprove = async () => {
    setConfirmBulkOpen(false);
    setError("");
    try {
      const res = await apiRequest<{ ket_qua: any[] }>(
        "/api/v1/lo/chap-nhan-hang-loat",
        {
          method: "POST",
          body: JSON.stringify({ lo_ids: selectedIds, xac_nhan: true }),
        }
      );
      const okCount = (res.ket_qua || []).filter((r) => r.thanh_cong).length;
      setMsg(
        `Đã xử lý duyệt hàng loạt (mỗi lô 1 transaction): ${okCount}/${selectedIds.length} lô thành công.`
      );
      setSelectedIds([]);
      await loadLos();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lỗi duyệt hàng loạt.");
    }
  };

  const handleAction = async (
    loId: number,
    endpoint: string,
    body: Record<string, unknown> = { xac_nhan: true }
  ) => {
    setError("");
    setMsg("");
    try {
      const updated = await apiRequest(`/api/v1/lo/${loId}/${endpoint}`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setSelectedLo(updated);
      setMsg(`Thao tác '${endpoint}' thành công cho lô ${updated.ma_lo}.`);
      await loadLos();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Thao tác thất bại.");
    }
  };

  const handleReject = async () => {
    if (!selectedLo) return;
    setError("");
    const bienLoi = Object.entries(errorPlatesMap)
      .filter(([, reason]) => reason.trim())
      .map(([bid, reason]) => ({ bien_id: Number(bid), ly_do: reason.trim() }));
    try {
      const updated = await apiRequest(
        `/api/v1/lo/${selectedLo.id}/tu-choi`,
        {
          method: "POST",
          body: JSON.stringify({
            ly_do: rejectReason.trim(),
            bien_loi: bienLoi,
          }),
        }
      );
      setRejectModalOpen(false);
      setRejectReason("");
      setErrorPlatesMap({});
      setSelectedLo(updated);
      await loadLos();
      await loadPlates(selectedLo.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Từ chối lô thất bại.");
    }
  };

  const handleCreateLoTinh = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const created = await apiRequest("/api/v1/lo", {
        method: "POST",
        body: JSON.stringify({ loai: "TINH", so_cong_van: newSoCv.trim() }),
      });
      setNewSoCv("");
      await loadLos();
      setSelectedLo(created);
      await loadPlates(created.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lỗi tạo lô tỉnh.");
    }
  };

  const handleAddBienToLo = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedLo) return;
    setError("");
    try {
      await apiRequest(`/api/v1/lo/${selectedLo.id}/bien`, {
        method: "POST",
        body: JSON.stringify({ bien_so: newBien.trim() }),
      });
      setNewBien("");
      await loadPlates(selectedLo.id);
      await loadLos();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lỗi thêm biển.");
    }
  };

  return (
    <div>
      <h2>Duyệt Lô Xã trực thuộc & Quản lý Lô Tỉnh (FR-047, FR-049, FR-061, FR-062, FR-071)</h2>
      <div className="toolbar">
        <button
          type="button"
          className={`btn ${tab === "LO_XA" ? "" : "btn-secondary"}`}
          onClick={() => setTab("LO_XA")}
        >
          Lô Xã/Phường trực thuộc
        </button>
        <button
          type="button"
          className={`btn ${tab === "LO_TINH" ? "" : "btn-secondary"}`}
          onClick={() => setTab("LO_TINH")}
        >
          Lô Tỉnh (do Tỉnh tự nhập)
        </button>
      </div>

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

      <div style={{ display: "grid", gridTemplateColumns: "430px 1fr", gap: 16 }}>
        <div className="card">
          {tab === "LO_XA" ? (
            <div className="toolbar" style={{ justifyContent: "space-between" }}>
              <strong>Danh sách Lô Xã trực thuộc</strong>
              <button
                type="button"
                className="btn btn-success"
                disabled={selectedIds.length === 0}
                onClick={() => setConfirmBulkOpen(true)}
              >
                Chấp nhận hàng loạt ({selectedIds.length})
              </button>
            </div>
          ) : (
            <form onSubmit={handleCreateLoTinh} className="toolbar">
              <input
                className="input"
                placeholder="Số công văn lô tỉnh (VD: 07/CV)"
                value={newSoCv}
                onChange={(e) => setNewSoCv(e.target.value)}
                required
              />
              <button type="submit" className="btn">
                Tạo Lô Tỉnh
              </button>
            </form>
          )}

          <table className="data-table">
            <thead>
              <tr>
                {tab === "LO_XA" && <th>Chọn</th>}
                <th>Mã lô</th>
                <th>Đơn vị</th>
                <th>Trạng thái</th>
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
                  {tab === "LO_XA" && (
                    <td onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(l.id)}
                        onChange={() =>
                          setSelectedIds((prev) =>
                            prev.includes(l.id)
                              ? prev.filter((x) => x !== l.id)
                              : [...prev, l.id]
                          )
                        }
                      />
                    </td>
                  )}
                  <td>
                    <strong>{l.ma_lo}</strong>
                  </td>
                  <td>{l.don_vi || l.xa_ma || l.tinh_ma}</td>
                  <td>
                    <StatusBadge status={l.trang_thai} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          {!selectedLo ? (
            <p>Chọn một lô bên trái để xem chi tiết và phê duyệt / điều chỉnh.</p>
          ) : (
            <>
              <div className="toolbar" style={{ justifyContent: "space-between" }}>
                <h3 style={{ margin: 0 }}>
                  {selectedLo.ma_lo} — <StatusBadge status={selectedLo.trang_thai} />
                </h3>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {selectedLo.loai === "TINH" &&
                    ["Khởi tạo", "Từ chối"].includes(selectedLo.trang_thai) && (
                      <button
                        type="button"
                        className="btn"
                        onClick={() => void handleAction(selectedLo.id, "gui")}
                      >
                        Gửi duyệt
                      </button>
                    )}
                  {selectedLo.trang_thai === "Chờ phê duyệt" && (
                    <>
                      <button
                        type="button"
                        className="btn btn-success"
                        onClick={() => void handleAction(selectedLo.id, "duyet")}
                      >
                        Chấp nhận
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger"
                        onClick={() => setRejectModalOpen(true)}
                      >
                        Từ chối & đánh dấu biển lỗi
                      </button>
                    </>
                  )}
                  {selectedLo.trang_thai === "Chấp nhận" && (
                    <button
                      type="button"
                      className="btn btn-warning"
                      onClick={() =>
                        void handleAction(selectedLo.id, "cho-phep-dieu-chinh")
                      }
                    >
                      Cho phép điều chỉnh (FR-049)
                    </button>
                  )}
                  {selectedLo.trang_thai === "Cho phép điều chỉnh" && (
                    <button
                      type="button"
                      className="btn btn-success"
                      onClick={() =>
                        void handleAction(selectedLo.id, "hoan-tat-dieu-chinh")
                      }
                    >
                      Hoàn tất điều chỉnh
                    </button>
                  )}
                </div>
              </div>

              {(selectedLo.trang_thai === "Cho phép điều chỉnh" ||
                (selectedLo.loai === "TINH" &&
                  ["Khởi tạo", "Từ chối"].includes(selectedLo.trang_thai))) && (
                <form onSubmit={handleAddBienToLo} className="toolbar">
                  <input
                    className="input"
                    placeholder="Thêm biển số vào lô (VD: 30A-123.45)"
                    value={newBien}
                    onChange={(e) => setNewBien(e.target.value)}
                    required
                  />
                  <button type="submit" className="btn">
                    Thêm biển
                  </button>
                </form>
              )}

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
                  {plates.map((p) => (
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
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      </div>

      <ConfirmModal
        open={confirmBulkOpen}
        title="Xác nhận Chấp nhận hàng loạt lô xã (FR-061, FR-091)"
        onConfirm={() => void handleBulkApprove()}
        onCancel={() => setConfirmBulkOpen(false)}
      >
        <p>
          Hệ thống sẽ phê duyệt {selectedIds.length} lô xã đã chọn (mỗi lô xử lý trong một transaction độc lập). Bạn có chắc chắn muốn thực hiện?
        </p>
      </ConfirmModal>

      {rejectModalOpen && (
        <div className="modal-backdrop">
          <div className="modal-box">
            <h3 style={{ marginTop: 0 }}>
              Từ chối lô & Đánh dấu biển lỗi (FR-047)
            </h3>
            <label style={{ display: "block", fontWeight: 600, marginBottom: 4 }}>
              Lý do chung từ chối lô (bắt buộc):
            </label>
            <textarea
              style={{ width: "100%", minHeight: 60, marginBottom: 12 }}
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
            />
            <div style={{ maxHeight: 220, overflow: "auto", marginBottom: 12 }}>
              {plates.map((p) => (
                <div
                  key={p.id}
                  style={{
                    display: "flex",
                    gap: 8,
                    alignItems: "center",
                    marginBottom: 6,
                  }}
                >
                  <strong style={{ width: 130 }}>{p.bien_so_day_du}</strong>
                  <input
                    className="input"
                    style={{ flex: 1 }}
                    placeholder="Lý do lỗi của biển này (nếu có)"
                    value={errorPlatesMap[p.id] || ""}
                    onChange={(e) =>
                      setErrorPlatesMap((prev) => ({
                        ...prev,
                        [p.id]: e.target.value,
                      }))
                    }
                  />
                </div>
              ))}
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setRejectModalOpen(false)}
              >
                Hủy
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={() => void handleReject()}
              >
                Xác nhận Từ chối
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
