import { FormEvent, useEffect, useState } from "react";
import { ApiError, apiRequest } from "../../api/client";
import { ConfirmModal, StatusBadge } from "../../components/ConfirmModal";

export function LoDnmPage() {
  const [dnms, setDnms] = useState<any[]>([]);
  const [eligibleChildren, setEligibleChildren] = useState<any[]>([]);
  const [selectedChildIds, setSelectedChildIds] = useState<number[]>([]);
  const [soCv, setSoCv] = useState("");
  const [selectedDnm, setSelectedDnm] = useState<any | null>(null);
  const [plates, setPlates] = useState<any[]>([]);

  const [cancelReason, setCancelReason] = useState("");
  const [confirmCancelOpen, setConfirmCancelOpen] = useState(false);
  const [confirmDatThanhCongOpen, setConfirmDatThanhCongOpen] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const loadData = async () => {
    const [dnmRes, xaRes, tinhRes] = await Promise.all([
      apiRequest<{ items: any[] }>("/api/v1/lo?loai=DAT_NHA_MAY"),
      apiRequest<{ items: any[] }>(
        "/api/v1/lo?loai=XA&trang_thai=Ch%E1%BA%A5p%20nh%E1%BA%ADn&chua_gan_dnm=true"
      ),
      apiRequest<{ items: any[] }>(
        "/api/v1/lo?loai=TINH&trang_thai=Ch%E1%BA%A5p%20nh%E1%BA%ADn&chua_gan_dnm=true"
      ),
    ]);
    setDnms(dnmRes.items || []);
    setEligibleChildren([...(xaRes.items || []), ...(tinhRes.items || [])]);
  };

  const loadPlates = async (dnmId: number) => {
    const res = await apiRequest<{ items: any[] }>(`/api/v1/lo/${dnmId}/bien`);
    setPlates(res.items || []);
  };

  useEffect(() => {
    void loadData();
  }, []);

  const handleCreateDnm = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const created = await apiRequest("/api/v1/lo", {
        method: "POST",
        body: JSON.stringify({
          loai: "DAT_NHA_MAY",
          so_cong_van: soCv.trim(),
          lo_con_ids: selectedChildIds,
        }),
      });
      setSoCv("");
      setSelectedChildIds([]);
      await loadData();
      setSelectedDnm(created);
      await loadPlates(created.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lỗi lập lô đặt nhà máy.");
    }
  };

  const handleAction = async (
    endpoint: string,
    body: Record<string, unknown> = { xac_nhan: true }
  ) => {
    if (!selectedDnm) return;
    setError("");
    try {
      const updated = await apiRequest(
        `/api/v1/lo/${selectedDnm.id}/${endpoint}`,
        {
          method: "POST",
          body: JSON.stringify(body),
        }
      );
      if (endpoint === "huy") {
        setMsg(`Đã hủy và xóa hoàn toàn lô đặt nhà máy ${selectedDnm.ma_lo}.`);
        setSelectedDnm(null);
        setPlates([]);
      } else {
        setSelectedDnm(updated);
        setMsg(`Đã thực hiện '${endpoint}' cho lô đặt nhà máy ${updated.ma_lo}.`);
      }
      setConfirmCancelOpen(false);
      setConfirmDatThanhCongOpen(false);
      await loadData();
      if (endpoint !== "huy") {
        await loadPlates(selectedDnm.id);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Thao tác thất bại.");
    }
  };

  return (
    <div>
      <h2>Quản lý Lô đặt nhà máy (FR-063..066, FR-069)</h2>
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

      <div style={{ display: "grid", gridTemplateColumns: "420px 1fr", gap: 16 }}>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Lập Lô đặt nhà máy mới</h3>
          <form onSubmit={handleCreateDnm}>
            <input
              className="input"
              style={{ width: "100%", marginBottom: 8 }}
              placeholder="Số công văn đặt nhà máy (dùng chung không gian mã với lô tỉnh)"
              value={soCv}
              onChange={(e) => setSoCv(e.target.value)}
              required
            />
            <div
              style={{
                maxHeight: 140,
                overflow: "auto",
                border: "1px solid var(--color-border)",
                padding: 8,
                marginBottom: 8,
              }}
            >
              <strong>Chọn các lô xã/lô tỉnh ở trạng thái Chấp nhận:</strong>
              {eligibleChildren.map((c) => (
                <label
                  key={c.id}
                  style={{ display: "block", marginTop: 4, cursor: "pointer" }}
                >
                  <input
                    type="checkbox"
                    checked={selectedChildIds.includes(c.id)}
                    onChange={() =>
                      setSelectedChildIds((prev) =>
                        prev.includes(c.id)
                          ? prev.filter((x) => x !== c.id)
                          : [...prev, c.id]
                      )
                    }
                  />{" "}
                  {c.ma_lo} ({c.loai} — {c.so_bien ?? 0} biển)
                </label>
              ))}
            </div>
            <button
              type="submit"
              className="btn"
              disabled={selectedChildIds.length === 0}
            >
              Tạo Lô đặt nhà máy ({selectedChildIds.length} lô thành phần)
            </button>
          </form>

          <hr style={{ margin: "16px 0" }} />
          <h3 style={{ marginTop: 0 }}>Danh sách Lô đặt nhà máy</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Mã lô ĐNM</th>
                <th>Trạng thái</th>
                <th>Số biển</th>
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
                  <td>{d.so_bien ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          {!selectedDnm ? (
            <p>Chọn một Lô đặt nhà máy bên trái để xem bảng biển số (7 cột) và duyệt.</p>
          ) : (
            <>
              <div className="toolbar" style={{ justifyContent: "space-between" }}>
                <h3 style={{ margin: 0 }}>
                  {selectedDnm.ma_lo} — <StatusBadge status={selectedDnm.trang_thai} />
                </h3>
                <div style={{ display: "flex", gap: 8 }}>
                  {selectedDnm.trang_thai === "Khởi tạo" && (
                    <button
                      type="button"
                      className="btn"
                      onClick={() => void handleAction("gui")}
                    >
                      Gửi duyệt
                    </button>
                  )}
                  {selectedDnm.trang_thai === "Chờ phê duyệt" && (
                    <>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => void handleAction("rut-ve")}
                      >
                        Rút về Khởi tạo
                      </button>
                      <button
                        type="button"
                        className="btn btn-success"
                        onClick={() => void handleAction("duyet")}
                      >
                        Tự duyệt (Chấp nhận)
                      </button>
                    </>
                  )}
                  {selectedDnm.trang_thai === "Chấp nhận" && (
                    <button
                      type="button"
                      className="btn btn-success"
                      onClick={() => setConfirmDatThanhCongOpen(true)}
                    >
                      Xác nhận Đặt nhà máy thành công (FR-066)
                    </button>
                  )}
                  {["Khởi tạo", "Chờ phê duyệt", "Chấp nhận"].includes(
                    selectedDnm.trang_thai
                  ) && (
                    <button
                      type="button"
                      className="btn btn-danger"
                      onClick={() => setConfirmCancelOpen(true)}
                    >
                      Hủy & Xóa lô đặt nhà máy
                    </button>
                  )}
                </div>
              </div>

              {/* Bảng biển 7 cột có thêm cột MÃ LÔ ĐẶT NHÀ MÁY ở cuối (FR-063) */}
              <table className="data-table">
                <thead>
                  <tr>
                    <th>STT</th>
                    <th>MÃ LÔ</th>
                    <th>ĐƠN VỊ</th>
                    <th>LOẠI PHƯƠNG TIỆN</th>
                    <th>MÀU SẮC</th>
                    <th>BIỂN SỐ ĐẦY ĐỦ</th>
                    <th>MÃ LÔ ĐẶT NHÀ MÁY</th>
                  </tr>
                </thead>
                <tbody>
                  {plates.map((p) => (
                    <tr key={p.id}>
                      <td>{p.stt}</td>
                      <td>{p.ma_lo}</td>
                      <td>{p.don_vi || p.don_vi_ten || "-"}</td>
                      <td>{p.loai_pt || p.loai_pt_ten || "-"}</td>
                      <td>{p.mau_sac}</td>
                      <td>
                        <strong>{p.bien_so_day_du}</strong>
                      </td>
                      <td>
                        <strong>
                          {p.ma_lo_dat_nha_may || selectedDnm.ma_lo}
                        </strong>
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
        open={confirmDatThanhCongOpen}
        title="Xác nhận đã đặt nhà máy thành công (FR-066)"
        onConfirm={() => void handleAction("dat-thanh-cong", { xac_nhan: true })}
        onCancel={() => setConfirmDatThanhCongOpen(false)}
      >
        <p>
          Khi xác nhận Đặt thành công, mọi lô thành phần chuyển sang Đặt thành công và mọi biển chuyển sang Đã đặt. Mọi điều chỉnh sau bước này đều bắt buộc xác nhận kèm lý do.
        </p>
      </ConfirmModal>

      <ConfirmModal
        open={confirmCancelOpen}
        title="Xác nhận Hủy & Xóa hẳn Lô đặt nhà máy"
        danger={true}
        onConfirm={() =>
          void handleAction("huy", {
            ly_do: cancelReason.trim(),
            xac_nhan: true,
          })
        }
        onCancel={() => setConfirmCancelOpen(false)}
      >
        <p>
          Lô đặt nhà máy sẽ được <strong>xóa hẳn khỏi hệ thống</strong> khi xác nhận hủy. Toàn bộ các lô thành phần (lô xã/lô tỉnh) sẽ được gỡ ra và giữ nguyên trạng thái Chấp nhận để gom lại đợt khác.
        </p>
        <label style={{ display: "block", fontWeight: 600, marginBottom: 4 }}>
          Lý do hủy (bắt buộc):
        </label>
        <textarea
          style={{ width: "100%", minHeight: 60 }}
          value={cancelReason}
          onChange={(e) => setCancelReason(e.target.value)}
          required
        />
      </ConfirmModal>
    </div>
  );
}

