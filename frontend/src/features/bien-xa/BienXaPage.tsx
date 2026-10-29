import { useEffect, useState } from "react";
import { ApiError, apiRequest, formatDateTimeVN } from "../../api/client";
import { ConfirmModal, StatusBadge } from "../../components/ConfirmModal";

export function BienXaPage() {
  const [items, setItems] = useState<any[]>([]);
  const [giaoFilter, setGiaoFilter] = useState("");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [lyDo, setLyDo] = useState("");
  const [modalMode, setModalMode] = useState<"TRA" | "THU_HOI" | "HUY" | null>(
    null
  );
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const loadData = async () => {
    const qs = giaoFilter ? `?giao=${encodeURIComponent(giaoFilter)}` : "";
    const res = await apiRequest<{ items: any[] }>(`/api/v1/bien-da-nhan${qs}`);
    setItems(res.items || []);
  };

  useEffect(() => {
    void loadData();
  }, [giaoFilter]);

  const toggleId = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const executeAction = async () => {
    setError("");
    setMsg("");
    try {
      if (modalMode === "TRA") {
        await apiRequest("/api/v1/bien/tra", {
          method: "POST",
          body: JSON.stringify({ bien_ids: selectedIds }),
        });
        setMsg(`Đã đánh dấu Đã trả cho ${selectedIds.length} biển số.`);
      } else if (modalMode === "THU_HOI") {
        await apiRequest("/api/v1/bien/thu-hoi", {
          method: "POST",
          body: JSON.stringify({
            bien_ids: selectedIds,
            ly_do: lyDo.trim(),
            xac_nhan: true,
          }),
        });
        setMsg(`Đã thu hồi ${selectedIds.length} biển số về xã.`);
      } else if (modalMode === "HUY") {
        await apiRequest("/api/v1/bien/huy", {
          method: "POST",
          body: JSON.stringify({
            bien_ids: selectedIds,
            ly_do: lyDo.trim(),
            xac_nhan: true,
          }),
        });
        setMsg(`Đã hủy ${selectedIds.length} biển số.`);
      }
      setModalMode(null);
      setSelectedIds([]);
      setLyDo("");
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Thao tác thất bại.");
    }
  };

  return (
    <div>
      <h2>Biển số đã nhận tại Xã/Phường — Trả dân, Thu hồi & Hủy (FR-052..054)</h2>
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

      <div className="card">
        <div className="toolbar" style={{ justifyContent: "space-between" }}>
          <div style={{ display: "flex", gap: 8 }}>
            <select
              className="select"
              value={giaoFilter}
              onChange={(e) => setGiaoFilter(e.target.value)}
            >
              <option value="">Tất cả trạng thái giao</option>
              <option value="Chưa trả">Chưa trả</option>
              <option value="Đã trả">Đã trả</option>
              <option value="Thu hồi về xã">Thu hồi về xã</option>
            </select>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              className="btn btn-success"
              disabled={selectedIds.length === 0}
              onClick={() => setModalMode("TRA")}
            >
              Trả biển cho người dân ({selectedIds.length})
            </button>
            <button
              type="button"
              className="btn btn-warning"
              disabled={selectedIds.length === 0}
              onClick={() => setModalMode("THU_HOI")}
            >
              Thu hồi về xã ({selectedIds.length})
            </button>
            <button
              type="button"
              className="btn btn-danger"
              disabled={selectedIds.length === 0}
              onClick={() => setModalMode("HUY")}
            >
              Hủy biển ({selectedIds.length})
            </button>
          </div>
        </div>

        <table className="data-table">
          <thead>
            <tr>
              <th>Chọn</th>
              <th>Biển số đầy đủ</th>
              <th>Mã lô</th>
              <th>Loại PT</th>
              <th>Màu sắc</th>
              <th>Số biên bản nhận</th>
              <th>Ngày nhận</th>
              <th>Trạng thái giao</th>
              <th>Ngày giờ trả</th>
            </tr>
          </thead>
          <tbody>
            {items.map((b) => (
              <tr key={b.id}>
                <td>
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(b.id)}
                    onChange={() => toggleId(b.id)}
                  />
                </td>
                <td>
                  <strong>{b.bien_so_day_du}</strong>
                </td>
                <td>{b.ma_lo}</td>
                <td>{b.loai_pt}</td>
                <td>{b.mau_sac}</td>
                <td>{b.so_bien_ban || "—"}</td>
                <td>{b.ngay_nhan || "—"}</td>
                <td>
                  <StatusBadge status={b.giao} />
                </td>
                <td>{formatDateTimeVN(b.ngay_gio_tra)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ConfirmModal
        open={modalMode !== null}
        title={
          modalMode === "TRA"
            ? "Xác nhận trả biển cho người dân (FR-053)"
            : modalMode === "THU_HOI"
            ? "Xác nhận thu hồi biển về xã (FR-054)"
            : "Xác nhận hủy biển tại xã (FR-054)"
        }
        danger={modalMode === "HUY"}
        onConfirm={() => void executeAction()}
        onCancel={() => setModalMode(null)}
      >
        {modalMode === "TRA" ? (
          <p>
            Đánh dấu <strong>Đã trả</strong> cho {selectedIds.length} biển đã chọn (hệ thống không lưu thông tin cá nhân công dân theo NFR-014).
          </p>
        ) : (
          <div>
            <label style={{ display: "block", fontWeight: 600, marginBottom: 6 }}>
              Lý do bắt buộc:
            </label>
            <textarea
              style={{ width: "100%", minHeight: 70 }}
              value={lyDo}
              onChange={(e) => setLyDo(e.target.value)}
              required
            />
          </div>
        )}
      </ConfirmModal>
    </div>
  );
}
