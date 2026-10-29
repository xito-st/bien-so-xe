import { FormEvent, useEffect, useState } from "react";
import { apiRequest } from "../../api/client";
import { StatusBadge } from "../../components/ConfirmModal";

export function TraCuuPage() {
  const [q, setQ] = useState("");
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [maLo, setMaLo] = useState("");
  const [bienSo, setBienSo] = useState("");
  const [seriChu, setSeriChu] = useState("");
  const [dauSo, setDauSo] = useState("");
  const [loaiPt, setLoaiPt] = useState("");
  const [maTinhBien, setMaTinhBien] = useState("");
  const [xaMa, setXaMa] = useState("");
  const [trangThaiLo, setTrangThaiLo] = useState("");
  const [tinhTrang, setTinhTrang] = useState("");
  const [ngoaiTinh, setNgoaiTinh] = useState("");
  const [items, setItems] = useState<any[]>([]);

  useEffect(() => {
    if (q.trim().length < 2) {
      setSuggestions([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await apiRequest<{ items: any[] }>(
          `/api/v1/bien/goi-y?q=${encodeURIComponent(q.trim())}`
        );
        setSuggestions(res.items || []);
      } catch {
        setSuggestions([]);
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [q]);

  const buildQueryString = () => {
    const params = new URLSearchParams();
    if (q.trim()) params.set("q", q.trim());
    if (maLo.trim()) params.set("ma_lo", maLo.trim());
    if (bienSo.trim()) params.set("bien_so", bienSo.trim());
    if (seriChu.trim()) params.set("seri_chu", seriChu.trim());
    if (dauSo.trim()) params.set("dau_so", dauSo.trim());
    if (loaiPt.trim()) params.set("loai_pt", loaiPt.trim());
    if (maTinhBien.trim()) params.set("ma_tinh_bien", maTinhBien.trim());
    if (xaMa.trim()) params.set("xa_ma", xaMa.trim());
    if (trangThaiLo) params.set("trang_thai_lo", trangThaiLo);
    if (tinhTrang) params.set("tinh_trang", tinhTrang);
    if (ngoaiTinh !== "") params.set("ngoai_tinh", ngoaiTinh);
    return params.toString();
  };

  const runSearch = async (e?: FormEvent) => {
    e?.preventDefault();
    const qs = buildQueryString();
    const res = await apiRequest<{ items: any[] }>(
      `/api/v1/bien${qs ? `?${qs}` : ""}`
    );
    setItems(res.items || []);
  };

  useEffect(() => {
    void runSearch();
  }, []);

  const exportUrl = `/api/v1/bien/xuat?${buildQueryString()}`;

  return (
    <div>
      <h2>
        Tra cứu Biển số có gợi ý & Lọc kết hợp theo phạm vi quyền (FR-050, FR-060, FR-081, FR-082)
      </h2>

      <div className="card">
        <form onSubmit={runSearch}>
          <div className="toolbar">
            <div style={{ position: "relative", minWidth: 260 }}>
              <input
                className="input"
                style={{ width: "100%" }}
                placeholder="Gõ từ 2 ký tự để gợi ý nhanh..."
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
              {suggestions.length > 0 && (
                <div
                  style={{
                    position: "absolute",
                    top: "100%",
                    left: 0,
                    right: 0,
                    background: "#fff",
                    border: "1px solid var(--color-border)",
                    zIndex: 50,
                    maxHeight: 220,
                    overflow: "auto",
                    boxShadow: "var(--shadow-sm)",
                  }}
                >
                  {suggestions.map((s) => (
                    <div
                      key={s.id}
                      style={{
                        padding: "6px 10px",
                        cursor: "pointer",
                        borderBottom: "1px solid #f1f5f9",
                      }}
                      onClick={() => {
                        setBienSo(s.bien_so_day_du);
                        setSuggestions([]);
                      }}
                    >
                      <strong>{s.bien_so_day_du}</strong> — Lô: {s.ma_lo} ({s.loai_pt})
                    </div>
                  ))}
                </div>
              )}
            </div>

            <input
              className="input"
              placeholder="Mã lô"
              value={maLo}
              onChange={(e) => setMaLo(e.target.value)}
            />
            <input
              className="input"
              placeholder="Biển số đầy đủ"
              value={bienSo}
              onChange={(e) => setBienSo(e.target.value)}
            />
            <input
              className="input"
              style={{ width: 100 }}
              placeholder="SeriChữ"
              value={seriChu}
              onChange={(e) => setSeriChu(e.target.value)}
            />
            <input
              className="input"
              style={{ width: 100 }}
              placeholder="Đầu số"
              value={dauSo}
              onChange={(e) => setDauSo(e.target.value)}
            />
            <input
              className="input"
              style={{ width: 130 }}
              placeholder="Loại PT"
              value={loaiPt}
              onChange={(e) => setLoaiPt(e.target.value)}
            />
            <input
              className="input"
              style={{ width: 95 }}
              placeholder="Mã tỉnh biển"
              value={maTinhBien}
              onChange={(e) => setMaTinhBien(e.target.value)}
            />
            <input
              className="input"
              style={{ width: 110 }}
              placeholder="Mã xã"
              value={xaMa}
              onChange={(e) => setXaMa(e.target.value)}
            />
            <select
              className="select"
              value={trangThaiLo}
              onChange={(e) => setTrangThaiLo(e.target.value)}
            >
              <option value="">Trạng thái lô</option>
              <option value="Khởi tạo">Khởi tạo</option>
              <option value="Chờ phê duyệt">Chờ phê duyệt</option>
              <option value="Chấp nhận">Chấp nhận</option>
              <option value="Từ chối">Từ chối</option>
              <option value="Cho phép điều chỉnh">Cho phép điều chỉnh</option>
              <option value="Đặt thành công">Đặt thành công</option>
              <option value="Đã nhập kho">Đã nhập kho</option>
              <option value="Đã nhận">Đã nhận</option>
            </select>
            <select
              className="select"
              value={tinhTrang}
              onChange={(e) => setTinhTrang(e.target.value)}
            >
              <option value="">Tình trạng biển</option>
              <option value="Chưa đặt">Chưa đặt</option>
              <option value="Đã đặt">Đã đặt</option>
              <option value="Tồn kho tỉnh">Tồn kho tỉnh</option>
              <option value="Tồn kho xã">Tồn kho xã</option>
              <option value="Đã hủy">Đã hủy</option>
            </select>
            <select
              className="select"
              value={ngoaiTinh}
              onChange={(e) => setNgoaiTinh(e.target.value)}
            >
              <option value="">Tất cả cờ ngoại tỉnh</option>
              <option value="true">Chỉ biển ngoại tỉnh</option>
              <option value="false">Chỉ biển nội tỉnh</option>
            </select>

            <button type="submit" className="btn">
              Lọc kết quả
            </button>
            <a href={exportUrl} className="btn btn-secondary">
              Xuất Excel (.xlsx)
            </a>
          </div>
        </form>

        <table className="data-table">
          <thead>
            <tr>
              <th>STT</th>
              <th>MÃ LÔ</th>
              <th>MÃ LÔ ĐNM</th>
              <th>ĐƠN VỊ</th>
              <th>BIỂN SỐ ĐẦY ĐỦ</th>
              <th>LOẠI PHƯƠNG TIỆN</th>
              <th>MÀU SẮC</th>
              <th>TRẠNG THÁI LÔ</th>
              <th>TÌNH TRẠNG BIỂN</th>
              <th>TRẠNG THÁI GIAO</th>
              <th>NGOẠI TỈNH</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>{item.stt}</td>
                <td>{item.ma_lo}</td>
                <td>{item.ma_lo_dat_nha_may || "—"}</td>
                <td>{item.don_vi}</td>
                <td>
                  <strong>{item.bien_so_day_du}</strong>
                </td>
                <td>{item.loai_pt}</td>
                <td>{item.mau_sac}</td>
                <td>
                  <StatusBadge status={item.trang_thai_lo} />
                </td>
                <td>
                  <StatusBadge status={item.tinh_trang} />
                </td>
                <td>
                  <StatusBadge status={item.giao} />
                </td>
                <td>{item.ngoai_tinh ? "Có" : "Không"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

