import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
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
  const [newMauSac, setNewMauSac] = useState("TRẮNG");
  const [rejectReason, setRejectReason] = useState("");
  const [errorPlatesMap, setErrorPlatesMap] = useState<Record<number, string>>(
    {}
  );

  // Sửa / Xóa biển số và Xóa lô tỉnh (FR-071, FR-043)
  const [editingPlate, setEditingPlate] = useState<any | null>(null);
  const [editBienInput, setEditBienInput] = useState("");
  const [editMauSac, setEditMauSac] = useState("TRẮNG");
  const [editInlinePreview, setEditInlinePreview] = useState<any>(null);
  const [editConfirmReorderOpen, setEditConfirmReorderOpen] = useState(false);
  const [confirmDeletePlate, setConfirmDeletePlate] = useState<any | null>(null);
  const [confirmDeleteLoOpen, setConfirmDeleteLoOpen] = useState(false);

  const [confirmBulkOpen, setConfirmBulkOpen] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);

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

  useEffect(() => {
    if (!editBienInput.trim() || !selectedLo || !editingPlate) {
      setEditInlinePreview(null);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await apiRequest("/api/v1/bien/kiem-tra", {
          method: "POST",
          body: JSON.stringify({
            lo_id: selectedLo.id,
            bien_so: editBienInput,
            mau_sac: editMauSac,
            exclude_bien_id: editingPlate.id,
          }),
        });
        setEditInlinePreview(res);
      } catch {
        setEditInlinePreview(null);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [editBienInput, editMauSac, selectedLo, editingPlate]);

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
        body: JSON.stringify({ bien_so: newBien.trim(), mau_sac: newMauSac }),
      });
      setNewBien("");
      await loadPlates(selectedLo.id);
      await loadLos();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lỗi thêm biển.");
    }
  };

  const handleOpenEditPlate = (p: any) => {
    setEditingPlate(p);
    setEditBienInput(p.bien_so_day_du);
    setEditMauSac(p.mau_sac);
    setEditInlinePreview(null);
    setError("");
  };

  const handleSaveEditPlate = async (datLaiXacNhan = false) => {
    if (!editingPlate || !selectedLo) return;
    setError("");
    setMsg("");
    try {
      await apiRequest(`/api/v1/bien/${editingPlate.id}`, {
        method: "PUT",
        body: JSON.stringify({
          bien_so: editBienInput.trim(),
          mau_sac: editMauSac,
          dat_lai_xac_nhan: datLaiXacNhan,
        }),
      });
      setEditingPlate(null);
      setEditConfirmReorderOpen(false);
      setMsg(`Đã cập nhật biển số ${editBienInput.trim()} thành công.`);
      await loadPlates(selectedLo.id);
      await loadLos();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && !datLaiXacNhan) {
        setEditConfirmReorderOpen(true);
      } else {
        setError(err instanceof ApiError ? err.message : "Lỗi sửa biển số.");
      }
    }
  };

  const handleDeletePlate = async () => {
    if (!confirmDeletePlate || !selectedLo) return;
    const plateId = confirmDeletePlate.id;
    const plateNo = confirmDeletePlate.bien_so_day_du;
    setConfirmDeletePlate(null);
    setError("");
    setMsg("");
    try {
      await apiRequest(`/api/v1/bien/${plateId}`, { method: "DELETE" });
      setMsg(`Đã xóa biển số ${plateNo} khỏi lô.`);
      await loadPlates(selectedLo.id);
      await loadLos();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lỗi xóa biển số.");
    }
  };

  const handleDeleteLo = async () => {
    if (!selectedLo) return;
    setConfirmDeleteLoOpen(false);
    setError("");
    setMsg("");
    try {
      await apiRequest(`/api/v1/lo/${selectedLo.id}`, { method: "DELETE" });
      setMsg(`Đã xóa lô ${selectedLo.ma_lo} thành công.`);
      setSelectedLo(null);
      setPlates([]);
      await loadLos();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lỗi xóa lô.");
    }
  };

  const handleImportExcel = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedLo) return;
    setError("");
    setMsg("");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await apiRequest<{ so_luong_them: number; so_luong_trung: number }>(
        `/api/v1/lo/${selectedLo.id}/bien/import`,
        { method: "POST", body: formData }
      );
      setMsg(`Đã import ${res.so_luong_them ?? 0} biển số thành công.`);
      await loadPlates(selectedLo.id);
      await loadLos();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lỗi import Excel.");
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
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

      <div className="split-layout-wide">
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
                  <td>{l.don_vi || l.don_vi_ten || l.xa_ten || l.tinh_ten || l.xa_ma || l.tinh_ma}</td>
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
                  {selectedLo.loai === "TINH" && selectedLo.trang_thai === "Khởi tạo" && (
                    <button
                      type="button"
                      className="btn btn-danger"
                      onClick={() => setConfirmDeleteLoOpen(true)}
                    >
                      Xóa lô
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
                <div className="toolbar" style={{ flexWrap: "wrap", alignItems: "center" }}>
                  <form onSubmit={handleAddBienToLo} style={{ display: "inline-flex", gap: 8 }}>
                    <input
                      className="input"
                      placeholder="Thêm biển số vào lô (VD: 30A-123.45)"
                      value={newBien}
                      onChange={(e) => setNewBien(e.target.value)}
                      required
                    />
                    <select
                      className="select"
                      value={newMauSac}
                      onChange={(e) => setNewMauSac(e.target.value)}
                    >
                      <option value="TRẮNG">Nền TRẮNG</option>
                      <option value="VÀNG">Nền VÀNG</option>
                      <option value="XANH">Nền XANH</option>
                    </select>
                    <button type="submit" className="btn">
                      Thêm biển
                    </button>
                  </form>
                  <a
                    href="/api/v1/import/file-mau.xlsx"
                    className="btn btn-secondary"
                    download="mau-nhap-bien-so.xlsx"
                  >
                    Tải file mẫu (.xlsx)
                  </a>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    Import Excel (.xlsx)
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".xlsx"
                    style={{ display: "none" }}
                    onChange={handleImportExcel}
                  />
                </div>
              )}

              {(() => {
                const canEdit =
                  (selectedLo.loai === "TINH" &&
                    ["Khởi tạo", "Từ chối", "Cho phép điều chỉnh"].includes(
                      selectedLo.trang_thai
                    )) ||
                  (selectedLo.loai === "XA" &&
                    selectedLo.trang_thai === "Cho phép điều chỉnh");
                return (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>STT</th>
                        <th>MÃ LÔ</th>
                        <th>ĐƠN VỊ</th>
                        <th>LOẠI PHƯƠNG TIỆN</th>
                        <th>MÀU SẮC</th>
                        <th>BIỂN SỐ ĐẦY ĐỦ</th>
                        {canEdit && <th>THAO TÁC</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {plates.map((p) => (
                        <tr key={p.id}>
                          <td>{p.stt}</td>
                          <td>{p.ma_lo}</td>
                          <td>{p.don_vi || p.don_vi_ten || p.xa_ten || p.tinh_ten || "-"}</td>
                          <td>{p.loai_pt || p.loai_pt_ten || "-"}</td>
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
                          {canEdit && (
                            <td>
                              <div style={{ display: "flex", gap: 6 }}>
                                <button
                                  type="button"
                                  className="btn btn-secondary"
                                  style={{ padding: "2px 8px", fontSize: 12 }}
                                  onClick={() => handleOpenEditPlate(p)}
                                >
                                  Sửa
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-danger"
                                  style={{ padding: "2px 8px", fontSize: 12 }}
                                  onClick={() => setConfirmDeletePlate(p)}
                                >
                                  Xóa
                                </button>
                              </div>
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                );
              })()}
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
      {/* Modal Sửa Biển số (FR-071, FR-043) */}
      {editingPlate && (
        <div className="modal-backdrop">
          <div className="modal-box" style={{ maxWidth: 480 }}>
            <h3 style={{ marginTop: 0 }}>Sửa biển số trong lô (FR-071)</h3>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: "block", fontWeight: 600, marginBottom: 4 }}>
                Biển số
              </label>
              <input
                className="input"
                style={{ width: "100%" }}
                value={editBienInput}
                onChange={(e) => setEditBienInput(e.target.value)}
                autoFocus
              />
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: "block", fontWeight: 600, marginBottom: 4 }}>
                Nền biển / Màu sắc
              </label>
              <select
                className="select"
                style={{ width: "100%" }}
                value={editMauSac}
                onChange={(e) => setEditMauSac(e.target.value)}
              >
                <option value="TRẮNG">Nền TRẮNG, chữ và số ĐEN</option>
                <option value="VÀNG">Nền VÀNG, chữ và số ĐEN</option>
                <option value="XANH">Nền XANH, chữ và số TRẮNG</option>
              </select>
            </div>
            {editInlinePreview && (
              <div
                style={{
                  fontSize: 13,
                  marginBottom: 12,
                  padding: 8,
                  background: "#f8fafc",
                  borderRadius: 4,
                }}
              >
                {editInlinePreview.hop_le ? (
                  <span>
                    Chuẩn hóa: <strong>{editInlinePreview.bien_so_day_du}</strong> | Loại PT:{" "}
                    <strong>{editInlinePreview.loai_pt}</strong> | Màu sắc:{" "}
                    <strong>{editInlinePreview.mau_sac}</strong>
                    {editInlinePreview.ngoai_tinh && (
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
                    {editInlinePreview.loi}
                  </span>
                )}
              </div>
            )}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setEditingPlate(null)}
              >
                Hủy
              </button>
              <button
                type="button"
                className="btn"
                disabled={
                  !editBienInput.trim() ||
                  (editInlinePreview && !editInlinePreview.hop_le)
                }
                onClick={() => void handleSaveEditPlate(false)}
              >
                Lưu thay đổi
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Xác nhận đặt lại khi Sửa biển (FR-036 mục d) */}
      <ConfirmModal
        open={editConfirmReorderOpen}
        title="Xác nhận đặt lại biển số đã trả / thu hồi (FR-036 mục d)"
        onConfirm={() => void handleSaveEditPlate(true)}
        onCancel={() => setEditConfirmReorderOpen(false)}
      >
        <p>
          Biển số này từng ở trạng thái Đã trả hoặc Thu hồi trong tỉnh. Bạn có xác nhận muốn đặt lại biển số này không?
        </p>
      </ConfirmModal>

      {/* Modal Xác nhận xóa biển (FR-071, FR-043) */}
      <ConfirmModal
        open={!!confirmDeletePlate}
        title="Xác nhận xóa biển số khỏi lô (FR-071)"
        danger={true}
        onConfirm={() => void handleDeletePlate()}
        onCancel={() => setConfirmDeletePlate(null)}
      >
        <p>
          Bạn có chắc chắn muốn xóa biển số <strong>{confirmDeletePlate?.bien_so_day_du}</strong> khỏi lô này không?
        </p>
      </ConfirmModal>

      {/* Modal Xác nhận xóa toàn bộ lô (FR-071) */}
      <ConfirmModal
        open={confirmDeleteLoOpen}
        title="Xác nhận xóa toàn bộ lô (FR-071)"
        danger={true}
        onConfirm={() => void handleDeleteLo()}
        onCancel={() => setConfirmDeleteLoOpen(false)}
      >
        <p>
          Lô <strong>{selectedLo?.ma_lo}</strong> đang ở trạng thái Khởi tạo. Khi xóa, toàn bộ biển số trong lô sẽ bị xóa và mã lô được giải phóng. Bạn có chắc chắn muốn xóa?
        </p>
      </ConfirmModal>
    </div>
  );
}

