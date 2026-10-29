import { useEffect, useState } from "react";
import { ApiError, apiRequest } from "../../api/client";
import { ConfirmModal, StatusBadge } from "../../components/ConfirmModal";

export function KhoTinhPage() {
  const [dnms, setDnms] = useState<any[]>([]);
  const [selectedDnm, setSelectedDnm] = useState<any | null>(null);
  const [plates, setPlates] = useState<any[]>([]);
  const [selectedPlateIds, setSelectedPlateIds] = useState<number[]>([]);

  // Điều chỉnh sau Đặt thành công (FR-066)
  const [adjLoConId, setAdjLoConId] = useState<number | "">("");
  const [adjBienSo, setAdjBienSo] = useState("");
  const [adjLyDo, setAdjLyDo] = useState("");
  const [confirmAdjustOpen, setConfirmAdjustOpen] = useState(false);

  // Chuyển xã từng phần (FR-068)
  const [chuyenLoXaId, setChuyenLoXaId] = useState<number | "">("");
  const [soBienBan, setSoBienBan] = useState("");
  const [nguoiNhan, setNguoiNhan] = useState("");
  const [chucVu, setChucVu] = useState("");
  const [ngayNhan, setNgayNhan] = useState(
    new Date().toISOString().slice(0, 10)
  );
  const [confirmChuyenOpen, setConfirmChuyenOpen] = useState(false);

  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const loadDnms = async () => {
    const res = await apiRequest<{ items: any[] }>(
      "/api/v1/lo?loai=DAT_NHA_MAY"
    );
    const active = (res.items || []).filter((d) =>
      ["Đặt thành công", "Đã nhập kho", "Đã chuyển Xã/phường"].includes(
        d.trang_thai
      )
    );
    setDnms(active);
  };

  const loadPlates = async (dnmId: number) => {
    const res = await apiRequest<{ items: any[] }>(`/api/v1/lo/${dnmId}/bien`);
    setPlates(res.items || []);
  };

  useEffect(() => {
    void loadDnms();
  }, []);

  const handleNhapKho = async (caLo: boolean) => {
    if (!selectedDnm) return;
    setError("");
    try {
      const updated = await apiRequest(
        `/api/v1/lo/${selectedDnm.id}/nhap-kho`,
        {
          method: "POST",
          body: JSON.stringify({
            ca_lo: caLo,
            bien_ids: caLo ? undefined : selectedPlateIds,
          }),
        }
      );
      setSelectedDnm(updated);
      setSelectedPlateIds([]);
      setMsg("Đã nhập kho tỉnh thành công.");
      await loadDnms();
      await loadPlates(selectedDnm.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lỗi nhập kho tỉnh.");
    }
  };

  const handleFactoryImport = async (file: File) => {
    if (!selectedDnm) return;
    setError("");
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await apiRequest<any>(
        `/api/v1/lo/${selectedDnm.id}/nhap-kho/import`,
        {
          method: "POST",
          body: fd,
        }
      );
      setMsg(
        `Đã import file nhà máy trả về: nhập kho ${res.so_bien_nhap_kho ?? 0} biển.`
      );
      await loadDnms();
      await loadPlates(selectedDnm.id);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Import file nhà máy trả về thất bại (tất cả hoặc không)."
      );
    }
  };

  const handlePostOrderAdd = async () => {
    if (!selectedDnm || !adjLoConId) return;
    setConfirmAdjustOpen(false);
    setError("");
    try {
      await apiRequest(`/api/v1/lo/${selectedDnm.id}/dieu-chinh-sau-dat`, {
        method: "POST",
        body: JSON.stringify({
          hanh_dong: "THEM_BIEN",
          lo_con_id: Number(adjLoConId),
          bien_so: adjBienSo.trim(),
          ly_do: adjLyDo.trim(),
          xac_nhan: true,
        }),
      });
      setAdjBienSo("");
      setAdjLyDo("");
      setMsg("Đã bổ sung biển sau Đặt thành công và ghi lịch sử/audit log.");
      await loadPlates(selectedDnm.id);
      await loadDnms();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Điều chỉnh thất bại.");
    }
  };

  const handleChuyenXa = async () => {
    if (!chuyenLoXaId) return;
    setConfirmChuyenOpen(false);
    setError("");
    try {
      await apiRequest(`/api/v1/lo/${chuyenLoXaId}/chuyen-xa`, {
        method: "POST",
        body: JSON.stringify({
          bien_ids: selectedPlateIds,
          so_bien_ban: soBienBan.trim(),
          nguoi_nhan: nguoiNhan.trim(),
          chuc_vu: chucVu.trim(),
          ngay_nhan: ngayNhan,
          xac_nhan: true,
        }),
      });
      setSelectedPlateIds([]);
      setSoBienBan("");
      setNguoiNhan("");
      setChucVu("");
      setMsg("Đã bàn giao biển số từng phần về Xã/Phường.");
      if (selectedDnm) {
        await loadPlates(selectedDnm.id);
      }
      await loadDnms();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Chuyển xã thất bại.");
    }
  };

  return (
    <div>
      <h2>
        Quản lý Kho Tỉnh, Import Nhà máy trả về & Bàn giao Xã từng phần (FR-066..068, FR-070, FR-072)
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

      <div style={{ display: "grid", gridTemplateColumns: "380px 1fr", gap: 16 }}>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Lô đặt nhà máy & Tiến độ nhập kho</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Mã lô ĐNM</th>
                <th>Trạng thái</th>
                <th>Tiến độ n/m</th>
              </tr>
            </thead>
            <tbody>
              {dnms.map((d) => (
                <tr
                  key={d.id}
                  style={{
                    cursor: "pointer",
                    background:
                      selectedDnm?.id === d.id ? "hsl(215, 70%, 95%)" : undefined,
                  }}
                  onClick={() => {
                    setSelectedDnm(d);
                    void loadPlates(d.id);
                  }}
                >
                  <td>
                    <strong>{d.ma_lo}</strong>
                  </td>
                  <td>
                    <StatusBadge status={d.trang_thai} />
                  </td>
                  <td>
                    {d.so_bien_da_nhap_kho ?? 0}/{d.so_bien ?? 0}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          {!selectedDnm ? (
            <p>Chọn một Lô đặt nhà máy bên trái để nhập kho, điều chỉnh sau đặt hoặc chuyển xã.</p>
          ) : (
            <>
              <div className="toolbar" style={{ justifyContent: "space-between" }}>
                <h3 style={{ margin: 0 }}>
                  {selectedDnm.ma_lo} — <StatusBadge status={selectedDnm.trang_thai} />
                </h3>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => void handleNhapKho(true)}
                  >
                    Nhập kho cả lô
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={selectedPlateIds.length === 0}
                    onClick={() => void handleNhapKho(false)}
                  >
                    Nhập kho biển đã chọn ({selectedPlateIds.length})
                  </button>
                  <label className="btn btn-secondary">
                    Import file nhà máy trả về (.xlsx)
                    <input
                      type="file"
                      accept=".xlsx"
                      style={{ display: "none" }}
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) void handleFactoryImport(f);
                      }}
                    />
                  </label>
                </div>
              </div>

              {/* Điều chỉnh sau Đặt thành công (FR-066) */}
              {selectedDnm.trang_thai === "Đặt thành công" && (
                <div className="card" style={{ background: "#f8fafc" }}>
                  <strong>Điều chỉnh sau Đặt thành công (FR-066 — bắt buộc xác nhận + lý do):</strong>
                  <div className="toolbar" style={{ marginTop: 6 }}>
                    <select
                      className="select"
                      value={adjLoConId}
                      onChange={(e) =>
                        setAdjLoConId(
                          e.target.value ? Number(e.target.value) : ""
                        )
                      }
                    >
                      <option value="">-- Chọn lô thành phần --</option>
                      {(selectedDnm.lo_con || []).map((c: any) => (
                        <option key={c.id} value={c.id}>
                          {c.ma_lo} ({c.loai})
                        </option>
                      ))}
                    </select>
                    <input
                      className="input"
                      placeholder="Biển số bổ sung"
                      value={adjBienSo}
                      onChange={(e) => setAdjBienSo(e.target.value)}
                    />
                    <input
                      className="input"
                      placeholder="Lý do điều chỉnh (bắt buộc)"
                      value={adjLyDo}
                      onChange={(e) => setAdjLyDo(e.target.value)}
                    />
                    <button
                      type="button"
                      className="btn btn-warning"
                      disabled={!adjLoConId || !adjBienSo || !adjLyDo}
                      onClick={() => setConfirmAdjustOpen(true)}
                    >
                      Bổ sung biển
                    </button>
                  </div>
                </div>
              )}

              {/* Chuyển xã từng phần với 4 trường bắt buộc (FR-068) */}
              <div className="card" style={{ background: "#f0fdf4" }}>
                <strong>
                  Chuyển biển Tồn kho tỉnh về Xã/Phường (FR-068 — bắt buộc đủ 4 trường biên bản):
                </strong>
                <div className="toolbar" style={{ marginTop: 6 }}>
                  <select
                    className="select"
                    value={chuyenLoXaId}
                    onChange={(e) =>
                      setChuyenLoXaId(
                        e.target.value ? Number(e.target.value) : ""
                      )
                    }
                  >
                    <option value="">-- Chọn lô xã thành phần --</option>
                    {(selectedDnm.lo_con || [])
                      .filter((c: any) => c.loai === "XA")
                      .map((c: any) => (
                        <option key={c.id} value={c.id}>
                          {c.ma_lo}
                        </option>
                      ))}
                  </select>
                  <input
                    className="input"
                    placeholder="1. Số biên bản nhận"
                    value={soBienBan}
                    onChange={(e) => setSoBienBan(e.target.value)}
                  />
                  <input
                    className="input"
                    placeholder="2. Người nhận"
                    value={nguoiNhan}
                    onChange={(e) => setNguoiNhan(e.target.value)}
                  />
                  <input
                    className="input"
                    placeholder="3. Chức vụ"
                    value={chucVu}
                    onChange={(e) => setChucVu(e.target.value)}
                  />
                  <input
                    type="date"
                    className="input"
                    value={ngayNhan}
                    onChange={(e) => setNgayNhan(e.target.value)}
                  />
                  <button
                    type="button"
                    className="btn btn-success"
                    disabled={
                      !chuyenLoXaId ||
                      selectedPlateIds.length === 0 ||
                      !soBienBan ||
                      !nguoiNhan ||
                      !chucVu
                    }
                    onClick={() => setConfirmChuyenOpen(true)}
                  >
                    Chuyển cho Xã ({selectedPlateIds.length} biển)
                  </button>
                </div>
              </div>

              <table className="data-table">
                <thead>
                  <tr>
                    <th>Chọn</th>
                    <th>Biển số đầy đủ</th>
                    <th>Mã lô nguồn</th>
                    <th>Đơn vị</th>
                    <th>Loại PT</th>
                    <th>Màu sắc</th>
                    <th>Tình trạng kho</th>
                    <th>Trạng thái giao</th>
                  </tr>
                </thead>
                <tbody>
                  {plates.map((p) => (
                    <tr key={p.id}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedPlateIds.includes(p.id)}
                          onChange={() =>
                            setSelectedPlateIds((prev) =>
                              prev.includes(p.id)
                                ? prev.filter((x) => x !== p.id)
                                : [...prev, p.id]
                            )
                          }
                        />
                      </td>
                      <td>
                        <strong>{p.bien_so_day_du}</strong>
                      </td>
                      <td>{p.ma_lo}</td>
                      <td>{p.don_vi}</td>
                      <td>{p.loai_pt}</td>
                      <td>{p.mau_sac}</td>
                      <td>
                        <StatusBadge status={p.tinh_trang} />
                      </td>
                      <td>
                        <StatusBadge status={p.giao} />
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
        open={confirmAdjustOpen}
        title="Xác nhận điều chỉnh sau Đặt thành công (FR-066)"
        onConfirm={() => void handlePostOrderAdd()}
        onCancel={() => setConfirmAdjustOpen(false)}
      >
        <p>
          Bổ sung biển <strong>{adjBienSo}</strong> với lý do:{" "}
          <em>{adjLyDo}</em>. Lô đặt nhà máy giữ trạng thái Đặt thành công và thao tác được ghi vào lịch sử lô + audit log.
        </p>
      </ConfirmModal>

      <ConfirmModal
        open={confirmChuyenOpen}
        title="Xác nhận bàn giao biển số cho Xã/Phường (FR-068, FR-091)"
        onConfirm={() => void handleChuyenXa()}
        onCancel={() => setConfirmChuyenOpen(false)}
      >
        <p>
          Bàn giao {selectedPlateIds.length} biển số theo biên bản{" "}
          <strong>{soBienBan}</strong> cho người nhận{" "}
          <strong>{nguoiNhan}</strong> ({chucVu}) ngày {ngayNhan}.
        </p>
      </ConfirmModal>
    </div>
  );
}
