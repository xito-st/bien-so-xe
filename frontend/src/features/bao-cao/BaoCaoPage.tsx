import { useEffect, useMemo, useRef, useState } from "react";
import { apiRequest } from "../../api/client";
import { StatusBadge } from "../../components/ConfirmModal";
import { useAuth } from "../auth/AuthContext";

type ReportType = "R1" | "R2" | "R3" | "R4" | "R5";

interface SelectedDrilldown {
  tableType: "LO" | "BIEN" | "R2" | "R4";
  title: string;
  unitName: string;
  badgeText: string;
  badgeClass: string;
  params: Record<string, any>;
}

interface ReportTabConfig {
  code: ReportType;
  title: string;
  badge: string;
  description: string;
}

const REPORT_TABS: ReportTabConfig[] = [
  {
    code: "R1",
    title: "Tổng quan Lô & Biển",
    badge: "R1",
    description: "Thống kê số lượng Lô và Biển số theo từng trạng thái vòng đời.",
  },
  {
    code: "R2",
    title: "Tồn kho Loại PT & Seri",
    badge: "R2",
    description: "Thống kê tồn kho tại Tỉnh & Xã/phường theo Loại phương tiện và Seri chữ.",
  },
  {
    code: "R3",
    title: "Tiến độ Đặt & Cấp phát",
    badge: "R3",
    description: "Theo dõi tiến độ qua 5 giai đoạn: Chờ duyệt, Đã duyệt, Đặt nhà máy, Nhập kho, Đã nhận.",
  },
  {
    code: "R4",
    title: "Tình hình Cấp trả Biển",
    badge: "R4",
    description: "Tỷ lệ Chưa trả (tồn kho), Đã cấp cho người dân, Thu hồi về xã theo từng đơn vị.",
  },
  {
    code: "R5",
    title: "Biển Hủy & Thu hồi",
    badge: "R5",
    description: "Danh sách chi tiết và tổng hợp các biển số bị hủy hoặc thu hồi kèm lý do.",
  },
];

export function BaoCaoPage() {
  const { user } = useAuth();

  const [reportCode, setReportCode] = useState<ReportType>("R1");
  const [tinhMa, setTinhMa] = useState("");
  const [xaMa, setXaMa] = useState("");
  const [tuNgay, setTuNgay] = useState("");
  const [denNgay, setDenNgay] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  const [tinhList, setTinhList] = useState<{ ma: string; ten: string }[]>([]);
  const [xaList, setXaList] = useState<{ ma: string; ten: string; tinh_ma: string }[]>([]);

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Khởi tạo bộ lọc theo phạm vi người dùng đăng nhập
  useEffect(() => {
    if (user) {
      if (user.vai_tro === "XA") {
        setTinhMa(user.tinh_ma || "");
        setXaMa(user.xa_ma || "");
      } else if (user.vai_tro === "TINH") {
        setTinhMa(user.tinh_ma || "");
      }
    }
  }, [user]);

  // Tải danh mục tỉnh
  useEffect(() => {
    const loadTinh = async () => {
      try {
        const res = await apiRequest<{ items: { ma: string; ten: string }[] }>(
          "/api/v1/danh-muc/tinh"
        );
        setTinhList(res.items || []);
      } catch {
        setTinhList([]);
      }
    };
    void loadTinh();
  }, []);

  // Tải danh mục xã/phường khi tinhMa thay đổi
  useEffect(() => {
    const loadXa = async () => {
      if (!tinhMa) {
        setXaList([]);
        return;
      }
      try {
        const res = await apiRequest<{
          items: { ma: string; ten: string; tinh_ma: string }[];
        }>(`/api/v1/danh-muc/xa?tinh_ma=${tinhMa}`);
        setXaList(res.items || []);
      } catch {
        setXaList([]);
      }
    };
    void loadXa();
  }, [tinhMa]);

  const buildQs = () => {
    const p = new URLSearchParams();
    if (tinhMa.trim()) p.set("tinh_ma", tinhMa.trim());
    if (xaMa.trim()) p.set("xa_ma", xaMa.trim());
    if (tuNgay.trim()) p.set("tu_ngay", `${tuNgay.trim()}T00:00:00`);
    if (denNgay.trim()) p.set("den_ngay", `${denNgay.trim()}T23:59:59`);
    return p.toString();
  };

  const loadReport = async () => {
    setLoading(true);
    setError("");
    setSelectedDrilldown(null);
    setDrilldownPlates([]);
    try {
      const qs = buildQs();
      const res = await apiRequest(
        `/api/v1/bao-cao/${reportCode}${qs ? `?${qs}` : ""}`
      );
      setData(res);
    } catch (err: any) {
      setError(err?.message || "Không thể tải dữ liệu báo cáo.");
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadReport();
  }, [reportCode]);

  const handleResetFilters = () => {
    if (user?.vai_tro === "ADMIN") {
      setTinhMa("");
      setXaMa("");
    } else if (user?.vai_tro === "TINH") {
      setXaMa("");
    }
    setTuNgay("");
    setDenNgay("");
    setSearchTerm("");
    setSelectedDrilldown(null);
    setDrilldownPlates([]);
  };

  const exportUrl = `/api/v1/bao-cao/${reportCode}/xuat?${buildQs()}`;

  // Trạng thái tương tác Drill-down hiển thị danh sách biển số chi tiết
  const [selectedDrilldown, setSelectedDrilldown] = useState<SelectedDrilldown | null>(null);
  const [drilldownPlates, setDrilldownPlates] = useState<any[]>([]);
  const [loadingDrilldown, setLoadingDrilldown] = useState(false);
  const [drilldownSearch, setDrilldownSearch] = useState("");
  const drilldownRef = useRef<HTMLDivElement>(null);

  const filteredDrilldownPlates = useMemo(() => {
    if (!drilldownSearch.trim()) return drilldownPlates;
    const term = drilldownSearch.toLowerCase().trim();
    return drilldownPlates.filter((p: any) =>
      Object.values(p).some((v) =>
        String(v ?? "").toLowerCase().includes(term)
      )
    );
  }, [drilldownPlates, drilldownSearch]);

  const fetchDrilldown = async (drilldown: SelectedDrilldown) => {
    setSelectedDrilldown(drilldown);
    setLoadingDrilldown(true);
    setDrilldownSearch("");
    try {
      const qs = new URLSearchParams();
      Object.entries(drilldown.params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") {
          qs.set(k, String(v));
        }
      });
      const res = await apiRequest<{ items: any[]; total: number }>(
        `/api/v1/bao-cao/chi-tiet/bien?${qs.toString()}`
      );
      setDrilldownPlates(res.items || []);
      setTimeout(() => {
        drilldownRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }, 100);
    } catch (err) {
      console.error("Lỗi tải chi tiết biển số:", err);
      setDrilldownPlates([]);
    } finally {
      setLoadingDrilldown(false);
    }
  };

  const isLoRowSelected = (r: any) =>
    selectedDrilldown?.tableType === "LO" &&
    selectedDrilldown.params.loai_lo === r.loai &&
    selectedDrilldown.params.trang_thai_lo === r.trang_thai &&
    (selectedDrilldown.params.xa_ma || "") === (r.xa_ma || "");

  const handleToggleLoRow = (r: any) => {
    if (isLoRowSelected(r)) {
      setSelectedDrilldown(null);
      setDrilldownPlates([]);
      return;
    }
    fetchDrilldown({
      tableType: "LO",
      title: `Chi tiết Biển số theo ${r.loai_hien_thi || r.loai}`,
      unitName: r.don_vi || "—",
      badgeText: `Trạng thái lô: ${r.trang_thai}`,
      badgeClass: "badge-info",
      params: {
        loai_lo: r.loai,
        trang_thai_lo: r.trang_thai,
        tinh_ma: r.tinh_ma || tinhMa,
        xa_ma: r.xa_ma || "",
        is_cap_tinh: !r.xa_ma,
        tu_ngay: tuNgay ? `${tuNgay}T00:00:00` : undefined,
        den_ngay: denNgay ? `${denNgay}T23:59:59` : undefined,
      },
    });
  };

  const isBienRowSelected = (r: any) =>
    selectedDrilldown?.tableType === "BIEN" &&
    selectedDrilldown.params.tinh_trang === r.tinh_trang &&
    selectedDrilldown.params.giao === r.giao &&
    (selectedDrilldown.params.xa_ma || "") === (r.xa_ma || "");

  const handleToggleBienRow = (r: any) => {
    if (isBienRowSelected(r)) {
      setSelectedDrilldown(null);
      setDrilldownPlates([]);
      return;
    }
    fetchDrilldown({
      tableType: "BIEN",
      title: `Chi tiết Biển số theo Tình trạng: ${r.tinh_trang}`,
      unitName: r.don_vi || "—",
      badgeText: `Trạng thái giao: ${r.giao}`,
      badgeClass: "badge-success",
      params: {
        tinh_trang: r.tinh_trang,
        giao: r.giao,
        tinh_ma: r.tinh_ma || tinhMa,
        xa_ma: r.xa_ma || "",
        is_cap_tinh: !r.xa_ma,
        tu_ngay: tuNgay ? `${tuNgay}T00:00:00` : undefined,
        den_ngay: denNgay ? `${denNgay}T23:59:59` : undefined,
      },
    });
  };

  const isR2RowSelected = (r: any) =>
    selectedDrilldown?.tableType === "R2" &&
    selectedDrilldown.params.seri_chu === r.seri_chu &&
    selectedDrilldown.params.loai_pt === r.loai_pt &&
    (selectedDrilldown.params.xa_ma || "") === (r.xa_ma || "") &&
    selectedDrilldown.params.tinh_trang === r.tinh_trang;

  const handleToggleR2Row = (r: any) => {
    if (isR2RowSelected(r)) {
      setSelectedDrilldown(null);
      setDrilldownPlates([]);
      return;
    }
    fetchDrilldown({
      tableType: "R2",
      title: `Chi tiết Biển số Tồn kho: ${r.loai_pt} (Seri ${r.seri_chu})`,
      unitName: r.don_vi || "—",
      badgeText: `Tình trạng: ${r.tinh_trang}`,
      badgeClass: "badge-warning",
      params: {
        tinh_ma: r.tinh_ma || tinhMa,
        xa_ma: r.xa_ma || "",
        is_cap_tinh: !r.xa_ma,
        loai_pt: r.loai_pt,
        seri_chu: r.seri_chu,
        tinh_trang: r.tinh_trang,
        tu_ngay: tuNgay ? `${tuNgay}T00:00:00` : undefined,
        den_ngay: denNgay ? `${denNgay}T23:59:59` : undefined,
      },
    });
  };

  // Lọc dữ liệu trong bảng theo ô tìm kiếm
  const filteredRows = useMemo(() => {
    if (!data?.rows || !Array.isArray(data.rows)) return [];
    if (!searchTerm.trim()) return data.rows;
    const term = searchTerm.toLowerCase().trim();
    return data.rows.filter((r: any) =>
      Object.values(r).some((v) =>
        String(v ?? "").toLowerCase().includes(term)
      )
    );
  }, [data, searchTerm]);

  // Dữ liệu riêng biệt cho Báo cáo R1: Bảng 1 (Tiến độ Lô) & Bảng 2 (Tiến độ Biển)
  const filteredBangLo = useMemo(() => {
    const list =
      data?.bang_lo && Array.isArray(data.bang_lo)
        ? data.bang_lo
        : (data?.rows || []).filter((r: any) => r.nhom === "LÔ");
    if (!searchTerm.trim()) return list;
    const term = searchTerm.toLowerCase().trim();
    return list.filter((r: any) =>
      Object.values(r).some((v) =>
        String(v ?? "").toLowerCase().includes(term)
      )
    );
  }, [data, searchTerm]);

  const filteredBangBien = useMemo(() => {
    const list =
      data?.bang_bien && Array.isArray(data.bang_bien)
        ? data.bang_bien
        : (data?.rows || []).filter((r: any) => r.nhom === "BIỂN SỐ");
    if (!searchTerm.trim()) return list;
    const term = searchTerm.toLowerCase().trim();
    return list.filter((r: any) =>
      Object.values(r).some((v) =>
        String(v ?? "").toLowerCase().includes(term)
      )
    );
  }, [data, searchTerm]);

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ margin: "0 0 6px 0" }}>
          Báo cáo & Thống kê Phân hệ Biển số xe (FR-080, FR-081)
        </h2>
        <div style={{ color: "var(--color-text-muted)", fontSize: 13 }}>
          Xem các chỉ số tổng hợp, biểu đồ trực quan và trích xuất dữ liệu Excel chính xác theo phạm vi quyền được phân công.
        </div>
      </div>

      {/* Tabs chọn loại báo cáo trực quan */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 12,
          marginBottom: 16,
        }}
      >
        {REPORT_TABS.map((tab) => {
          const isActive = reportCode === tab.code;
          return (
            <button
              key={tab.code}
              type="button"
              onClick={() => {
                setReportCode(tab.code);
                setSearchTerm("");
              }}
              style={{
                textAlign: "left",
                background: isActive ? "#fff" : "#f8fafc",
                border: isActive
                  ? "2px solid var(--color-primary)"
                  : "1px solid var(--color-border)",
                borderRadius: "var(--radius-md)",
                padding: "12px 14px",
                cursor: "pointer",
                boxShadow: isActive ? "0 4px 12px rgba(27, 54, 93, 0.12)" : "none",
                transition: "all 0.18s ease-in-out",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span
                  style={{
                    display: "inline-block",
                    padding: "2px 8px",
                    borderRadius: 4,
                    fontSize: 11,
                    fontWeight: 700,
                    background: isActive ? "var(--color-primary)" : "#e2e8f0",
                    color: isActive ? "#fff" : "#475569",
                  }}
                >
                  {tab.badge}
                </span>
                <strong style={{ fontSize: 14, color: isActive ? "var(--color-primary)" : "inherit" }}>
                  {tab.title}
                </strong>
              </div>
              <div
                style={{
                  fontSize: 12,
                  color: "var(--color-text-muted)",
                  lineHeight: 1.4,
                  display: "-webkit-box",
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                }}
              >
                {tab.description}
              </div>
            </button>
          );
        })}
      </div>

      {/* Bộ lọc linh hoạt & nút Xuất Excel */}
      <div className="card" style={{ padding: 14, marginBottom: 16 }}>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 12,
            alignItems: "flex-end",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
            {/* Tỉnh / Thành */}
            <div>
              <label style={{ display: "block", fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                Tỉnh / Thành phố
              </label>
              <select
                className="select"
                style={{ minWidth: 190 }}
                value={tinhMa}
                onChange={(e) => {
                  setTinhMa(e.target.value);
                  setXaMa("");
                }}
                disabled={user?.vai_tro === "TINH" || user?.vai_tro === "XA"}
              >
                {user?.vai_tro === "ADMIN" && (
                  <option value="">-- Toàn quốc (34 Tỉnh) --</option>
                )}
                {tinhList.map((t) => (
                  <option key={t.ma} value={t.ma}>
                    {t.ten} ({t.ma})
                  </option>
                ))}
              </select>
            </div>

            {/* Xã / Phường */}
            <div>
              <label style={{ display: "block", fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                Xã / Phường / Thị trấn
              </label>
              <select
                className="select"
                style={{ minWidth: 210 }}
                value={xaMa}
                onChange={(e) => setXaMa(e.target.value)}
                disabled={user?.vai_tro === "XA" || (!tinhMa && user?.vai_tro === "ADMIN")}
              >
                <option value="">-- Tất cả Xã / Phường --</option>
                {xaList.map((x) => (
                  <option key={x.ma} value={x.ma}>
                    {x.ten} ({x.ma})
                  </option>
                ))}
              </select>
            </div>

            {/* Từ ngày */}
            <div>
              <label style={{ display: "block", fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                Từ ngày tạo
              </label>
              <input
                type="date"
                className="input"
                value={tuNgay}
                onChange={(e) => setTuNgay(e.target.value)}
              />
            </div>

            {/* Đến ngày */}
            <div>
              <label style={{ display: "block", fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                Đến ngày tạo
              </label>
              <input
                type="date"
                className="input"
                value={denNgay}
                onChange={(e) => setDenNgay(e.target.value)}
              />
            </div>

            <button
              type="button"
              className="btn"
              disabled={loading}
              onClick={() => void loadReport()}
            >
              {loading ? "Đang tải..." : "Xem báo cáo"}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleResetFilters}
            >
              Đặt lại
            </button>
          </div>

          <div>
            <a
              href={exportUrl}
              className="btn btn-success"
              style={{ fontWeight: 600 }}
              download
            >
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              Xuất Excel (.xlsx)
            </a>
          </div>
        </div>
      </div>

      {error && (
        <div className="card" style={{ color: "var(--color-danger)", fontWeight: 600 }}>
          {error}
        </div>
      )}

      {/* Dashboard KPI Thống kê trực quan theo từng báo cáo */}
      {data && (
        <div>
          {/* R1: Thẻ KPI Lô & Biển số */}
          {reportCode === "R1" && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
                gap: 14,
                marginBottom: 16,
              }}
            >
              <div
                className="card"
                style={{
                  margin: 0,
                  borderLeft: "4px solid var(--color-primary)",
                  padding: "14px 18px",
                }}
              >
                <div style={{ color: "var(--color-text-muted)", fontSize: 13, fontWeight: 500 }}>
                  Tổng số Lô toàn hệ thống
                </div>
                <div style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginTop: 4 }}>
                  {(data.tong_so_lo ?? 0).toLocaleString("vi-VN")}
                </div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
                  Bao gồm lô nhà máy, tỉnh và xã
                </div>
              </div>

              <div
                className="card"
                style={{
                  margin: 0,
                  borderLeft: "4px solid #0284c7",
                  padding: "14px 18px",
                }}
              >
                <div style={{ color: "var(--color-text-muted)", fontSize: 13, fontWeight: 500 }}>
                  Tổng số Biển số đã tạo
                </div>
                <div style={{ fontSize: 26, fontWeight: 700, color: "#0284c7", marginTop: 4 }}>
                  {(data.tong_so_bien ?? 0).toLocaleString("vi-VN")}
                </div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
                  Tổng biển trong các lô hiện hành
                </div>
              </div>

              <div
                className="card"
                style={{
                  margin: 0,
                  borderLeft: "4px solid var(--color-warning)",
                  padding: "14px 18px",
                }}
              >
                <div style={{ color: "var(--color-text-muted)", fontSize: 13, fontWeight: 500 }}>
                  Biển số trong Kho (Tỉnh + Xã)
                </div>
                <div style={{ fontSize: 26, fontWeight: 700, color: "var(--color-warning)", marginTop: 4 }}>
                  {(
                    (data.bien_theo_tinh_trang || [])
                      .filter((b: any) =>
                        ["Tồn kho tỉnh", "Tồn kho xã"].includes(b.tinh_trang)
                      )
                      .reduce((acc: number, cur: any) => acc + (cur.so_bien || 0), 0)
                  ).toLocaleString("vi-VN")}
                </div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
                  Sẵn sàng chờ cấp trả cho công dân
                </div>
              </div>

              <div
                className="card"
                style={{
                  margin: 0,
                  borderLeft: "4px solid var(--color-success)",
                  padding: "14px 18px",
                }}
              >
                <div style={{ color: "var(--color-text-muted)", fontSize: 13, fontWeight: 500 }}>
                  Biển số Đã trả công dân
                </div>
                <div style={{ fontSize: 26, fontWeight: 700, color: "var(--color-success)", marginTop: 4 }}>
                  {(
                    (data.bien_theo_tinh_trang || [])
                      .filter((b: any) => b.giao === "Đã trả")
                      .reduce((acc: number, cur: any) => acc + (cur.so_bien || 0), 0)
                  ).toLocaleString("vi-VN")}
                </div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
                  Đã hoàn thành bàn giao
                </div>
              </div>
            </div>
          )}

          {/* R2: Thẻ KPI Tồn kho Loại PT & Seri */}
          {reportCode === "R2" && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))",
                gap: 14,
                marginBottom: 16,
              }}
            >
              <div
                className="card"
                style={{
                  margin: 0,
                  borderLeft: "4px solid var(--color-primary)",
                  padding: "14px 18px",
                }}
              >
                <div style={{ color: "var(--color-text-muted)", fontSize: 13, fontWeight: 500 }}>
                  Tổng số Biển số Tồn kho
                </div>
                <div style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginTop: 4 }}>
                  {(data.tong_ton_kho ?? 0).toLocaleString("vi-VN")}
                </div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
                  Tổng biển hiện có tại kho Tỉnh và kho Xã
                </div>
              </div>

              <div
                className="card"
                style={{
                  margin: 0,
                  borderLeft: "4px solid #0284c7",
                  padding: "14px 18px",
                }}
              >
                <div style={{ color: "var(--color-text-muted)", fontSize: 13, fontWeight: 500 }}>
                  Tồn tại Kho Tỉnh
                </div>
                <div style={{ fontSize: 26, fontWeight: 700, color: "#0284c7", marginTop: 4 }}>
                  {(data.ton_kho_tinh ?? 0).toLocaleString("vi-VN")}
                </div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
                  Đang giữ tại kho cấp Tỉnh
                </div>
              </div>

              <div
                className="card"
                style={{
                  margin: 0,
                  borderLeft: "4px solid var(--color-success)",
                  padding: "14px 18px",
                }}
              >
                <div style={{ color: "var(--color-text-muted)", fontSize: 13, fontWeight: 500 }}>
                  Tồn tại Kho Xã / Phường
                </div>
                <div style={{ fontSize: 26, fontWeight: 700, color: "var(--color-success)", marginTop: 4 }}>
                  {(data.ton_kho_xa ?? 0).toLocaleString("vi-VN")}
                </div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
                  Đã bàn giao về cấp xã, sẵn sàng cấp
                </div>
              </div>
            </div>
          )}

          {/* R3: Visual Funnel / 5 Giai đoạn tiến độ */}
          {reportCode === "R3" && (
            <div className="card" style={{ marginBottom: 16, padding: "16px 20px" }}>
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 12 }}>
                Tiến độ luân chuyển qua 5 giai đoạn vòng đời (FR-080 R3)
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(5, 1fr)",
                  gap: 10,
                  textAlign: "center",
                }}
              >
                {[
                  { label: "1. Chờ phê duyệt", key: "cho_duyet", color: "#64748b" },
                  { label: "2. Đã duyệt", key: "da_duyet", color: "#0284c7" },
                  { label: "3. Đã đặt nhà máy", key: "da_dat", color: "#8b5cf6" },
                  { label: "4. Đã nhập kho tỉnh", key: "da_nhap_kho", color: "#f59e0b" },
                  { label: "5. Đã nhận về xã", key: "da_nhan", color: "#10b981" },
                ].map((st) => {
                  const cnt = data[st.key] ?? 0;
                  return (
                    <div
                      key={st.key}
                      style={{
                        padding: "12px 8px",
                        background: "#f8fafc",
                        border: "1px solid var(--color-border)",
                        borderTop: `4px solid ${st.color}`,
                        borderRadius: "var(--radius-sm)",
                      }}
                    >
                      <div style={{ fontSize: 12, fontWeight: 600, color: st.color }}>
                        {st.label}
                      </div>
                      <div style={{ fontSize: 22, fontWeight: 700, margin: "6px 0 2px" }}>
                        {cnt.toLocaleString("vi-VN")}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                        lô hoàn thành
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* R4: Thẻ KPI Cấp trả Biển */}
          {reportCode === "R4" && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
                gap: 14,
                marginBottom: 16,
              }}
            >
              <div
                className="card"
                style={{
                  margin: 0,
                  borderLeft: "4px solid var(--color-primary)",
                  padding: "14px 18px",
                }}
              >
                <div style={{ color: "var(--color-text-muted)", fontSize: 13, fontWeight: 500 }}>
                  Tổng số Biển trong đợt
                </div>
                <div style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginTop: 4 }}>
                  {(data.tong_so ?? 0).toLocaleString("vi-VN")}
                </div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
                  Toàn bộ biển thuộc phạm vi lọc
                </div>
              </div>

              <div
                className="card"
                style={{
                  margin: 0,
                  borderLeft: "4px solid #0284c7",
                  padding: "14px 18px",
                }}
              >
                <div style={{ color: "var(--color-text-muted)", fontSize: 13, fontWeight: 500 }}>
                  Chưa trả (Tồn tại Xã)
                </div>
                <div style={{ fontSize: 26, fontWeight: 700, color: "#0284c7", marginTop: 4 }}>
                  {(data.tong_chua_tra ?? 0).toLocaleString("vi-VN")}
                </div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
                  Sẵn sàng bàn giao cho người dân
                </div>
              </div>

              <div
                className="card"
                style={{
                  margin: 0,
                  borderLeft: "4px solid var(--color-success)",
                  padding: "14px 18px",
                }}
              >
                <div style={{ color: "var(--color-text-muted)", fontSize: 13, fontWeight: 500 }}>
                  Đã trả (Hoàn thành)
                </div>
                <div style={{ fontSize: 26, fontWeight: 700, color: "var(--color-success)", marginTop: 4 }}>
                  {(data.tong_da_tra ?? 0).toLocaleString("vi-VN")}
                </div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
                  Tỷ lệ cấp phát:{" "}
                  <strong>
                    {data.tong_so > 0
                      ? Math.round((data.tong_da_tra / data.tong_so) * 100)
                      : 0}
                    %
                  </strong>
                </div>
              </div>

              <div
                className="card"
                style={{
                  margin: 0,
                  borderLeft: "4px solid var(--color-warning)",
                  padding: "14px 18px",
                }}
              >
                <div style={{ color: "var(--color-text-muted)", fontSize: 13, fontWeight: 500 }}>
                  Thu hồi về xã
                </div>
                <div style={{ fontSize: 26, fontWeight: 700, color: "var(--color-warning)", marginTop: 4 }}>
                  {(data.tong_thu_hoi_ve_xa ?? 0).toLocaleString("vi-VN")}
                </div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
                  Biển thu hồi chờ tái cấp / xử lý
                </div>
              </div>
            </div>
          )}

          {/* R5: Thẻ KPI Hủy & Thu hồi */}
          {reportCode === "R5" && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                gap: 14,
                marginBottom: 16,
              }}
            >
              <div
                className="card"
                style={{
                  margin: 0,
                  borderLeft: "4px solid var(--color-primary)",
                  padding: "14px 18px",
                }}
              >
                <div style={{ color: "var(--color-text-muted)", fontSize: 13, fontWeight: 500 }}>
                  Tổng số Biển bị Hủy / Thu hồi
                </div>
                <div style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginTop: 4 }}>
                  {(data.tong_so ?? 0).toLocaleString("vi-VN")}
                </div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
                  Tổng số sự cố phát sinh
                </div>
              </div>

              <div
                className="card"
                style={{
                  margin: 0,
                  borderLeft: "4px solid var(--color-danger)",
                  padding: "14px 18px",
                }}
              >
                <div style={{ color: "var(--color-text-muted)", fontSize: 13, fontWeight: 500 }}>
                  Biển số Đã hủy
                </div>
                <div style={{ fontSize: 26, fontWeight: 700, color: "var(--color-danger)", marginTop: 4 }}>
                  {(data.tong_da_huy ?? 0).toLocaleString("vi-VN")}
                </div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
                  Bị lỗi in ấn / hư hỏng / hủy hợp lệ
                </div>
              </div>

              <div
                className="card"
                style={{
                  margin: 0,
                  borderLeft: "4px solid var(--color-warning)",
                  padding: "14px 18px",
                }}
              >
                <div style={{ color: "var(--color-text-muted)", fontSize: 13, fontWeight: 500 }}>
                  Thu hồi về xã
                </div>
                <div style={{ fontSize: 26, fontWeight: 700, color: "var(--color-warning)", marginTop: 4 }}>
                  {(data.tong_thu_hoi_ve_xa ?? 0).toLocaleString("vi-VN")}
                </div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
                  Thu hồi từ phương tiện / sang tên
                </div>
              </div>
            </div>
          )}

          {/* Bảng dữ liệu chi tiết chuyên nghiệp */}
          <div className="card">
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: 12,
                marginBottom: 12,
              }}
            >
              <div>
                <h3 style={{ margin: "0 0 4px" }}>{data.title}</h3>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
                  {reportCode === "R1" ? (
                    <>
                      Phân tách 2 bảng riêng biệt theo Đơn vị: Bảng Lô (
                      <strong>{filteredBangLo.length}</strong> dòng) và Bảng Biển (
                      <strong>{filteredBangBien.length}</strong> dòng)
                    </>
                  ) : (
                    <>
                      Hiển thị <strong>{filteredRows.length}</strong> dòng dữ liệu
                      {searchTerm && ` (được lọc từ tổng số ${data.rows?.length ?? 0} dòng)`}
                    </>
                  )}
                </div>
              </div>

              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input
                  className="input"
                  placeholder="Tìm nhanh trong bảng..."
                  style={{ width: 220 }}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </div>

            <div style={{ overflowX: "auto" }}>
              {/* Bảng R1: Tách riêng 2 bảng Lô và Biển theo Đơn vị & Tiến độ chuẩn */}
              {reportCode === "R1" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
                  {/* BẢNG 1: THEO LÔ */}
                  <div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        marginBottom: 10,
                        paddingBottom: 6,
                        borderBottom: "2px solid #0284c7",
                      }}
                    >
                      <span
                        style={{
                          background: "#0284c7",
                          color: "#fff",
                          fontWeight: 700,
                          fontSize: 12,
                          padding: "2px 8px",
                          borderRadius: 4,
                        }}
                      >
                        BẢNG 1
                      </span>
                      <h4 style={{ margin: 0, fontSize: 15, color: "#0f172a" }}>
                        Thống kê Tiến độ Lô theo từng Đơn vị
                      </h4>
                      <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
                        ({filteredBangLo.length} dòng dữ liệu)
                      </span>
                    </div>

                    <table className="data-table">
                      <thead>
                        <tr>
                          <th style={{ width: 60, textAlign: "center" }}>STT</th>
                          <th style={{ minWidth: 200 }}>ĐƠN VỊ</th>
                          <th style={{ width: 180 }}>LOẠI LÔ</th>
                          <th>TRẠNG THÁI TIẾN ĐỘ VÒNG ĐỜI</th>
                          <th style={{ width: 180, textAlign: "right" }}>SỐ LƯỢNG LÔ</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredBangLo.length === 0 ? (
                          <tr>
                            <td
                              colSpan={5}
                              style={{
                                textAlign: "center",
                                padding: 20,
                                color: "var(--color-text-muted)",
                              }}
                            >
                              Không có dữ liệu lô phù hợp.
                            </td>
                          </tr>
                        ) : (
                          filteredBangLo.map((r: any, idx: number) => {
                            const isSelected = isLoRowSelected(r);
                            return (
                              <tr
                                key={idx}
                                onClick={() => handleToggleLoRow(r)}
                                style={{
                                  cursor: "pointer",
                                  background: isSelected ? "#e0f2fe" : undefined,
                                  borderLeft: isSelected ? "4px solid var(--color-primary)" : "4px solid transparent",
                                  transition: "all 0.15s ease",
                                }}
                                title="Nhấp để xem danh sách chi tiết các biển số thuộc lô này"
                              >
                                <td style={{ textAlign: "center" }}>
                                  {isSelected ? "👉 " : ""}{idx + 1}
                                </td>
                                <td>
                                  <strong>{r.don_vi || "—"}</strong>
                                </td>
                                <td>
                                  <span className="badge badge-info" style={{ fontWeight: 600 }}>
                                    {r.loai_hien_thi || r.phan_loai || r.loai || "—"}
                                  </span>
                                </td>
                                <td>
                                  <StatusBadge status={r.trang_thai} />
                                </td>
                                <td
                                  style={{
                                    textAlign: "right",
                                    fontWeight: 600,
                                    color: "var(--color-primary)",
                                  }}
                                >
                                  <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                                    <span>{(r.so_luong ?? 0).toLocaleString("vi-VN")}</span>
                                    <button
                                      type="button"
                                      className="btn btn-secondary"
                                      style={{
                                        padding: "2px 8px",
                                        fontSize: 11,
                                        height: 24,
                                        borderRadius: 4,
                                        background: isSelected ? "var(--color-primary)" : "#f1f5f9",
                                        color: isSelected ? "#fff" : "var(--color-primary)",
                                        border: "1px solid #cbd5e1",
                                        cursor: "pointer",
                                      }}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleToggleLoRow(r);
                                      }}
                                    >
                                      {isSelected ? "Đang xem" : "Xem biển 🔍"}
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                      {filteredBangLo.length > 0 && (
                        <tfoot>
                          <tr style={{ background: "#f8fafc", fontWeight: 700 }}>
                            <td colSpan={4} style={{ textAlign: "right", paddingRight: 16 }}>
                              TỔNG SỐ LÔ THEO TIẾN ĐỘ:
                            </td>
                            <td
                              style={{
                                textAlign: "right",
                                color: "var(--color-primary)",
                                fontSize: 14,
                              }}
                            >
                              {filteredBangLo
                                .reduce((acc: number, cur: any) => acc + (cur.so_luong || 0), 0)
                                .toLocaleString("vi-VN")}
                            </td>
                          </tr>
                        </tfoot>
                      )}
                    </table>
                  </div>

                  {/* BẢNG 2: THEO BIỂN */}
                  <div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        marginBottom: 10,
                        paddingBottom: 6,
                        borderBottom: "2px solid #10b981",
                      }}
                    >
                      <span
                        style={{
                          background: "#10b981",
                          color: "#fff",
                          fontWeight: 700,
                          fontSize: 12,
                          padding: "2px 8px",
                          borderRadius: 4,
                        }}
                      >
                        BẢNG 2
                      </span>
                      <h4 style={{ margin: 0, fontSize: 15, color: "#0f172a" }}>
                        Thống kê Tình trạng & Tiến độ Cấp phát Biển số theo từng Đơn vị
                      </h4>
                      <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
                        ({filteredBangBien.length} dòng dữ liệu)
                      </span>
                    </div>

                    <table className="data-table">
                      <thead>
                        <tr>
                          <th style={{ width: 60, textAlign: "center" }}>STT</th>
                          <th style={{ minWidth: 200 }}>ĐƠN VỊ</th>
                          <th style={{ width: 200 }}>VỊ TRÍ / TÌNH TRẠNG KHO</th>
                          <th>TRẠNG THÁI CẤP PHÁT / BÀN GIAO</th>
                          <th style={{ width: 180, textAlign: "right" }}>SỐ LƯỢNG BIỂN</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredBangBien.length === 0 ? (
                          <tr>
                            <td
                              colSpan={5}
                              style={{
                                textAlign: "center",
                                padding: 20,
                                color: "var(--color-text-muted)",
                              }}
                            >
                              Không có dữ liệu biển số phù hợp.
                            </td>
                          </tr>
                        ) : (
                          filteredBangBien.map((r: any, idx: number) => {
                            const isSelected = isBienRowSelected(r);
                            return (
                              <tr
                                key={idx}
                                onClick={() => handleToggleBienRow(r)}
                                style={{
                                  cursor: "pointer",
                                  background: isSelected ? "#d1fae5" : undefined,
                                  borderLeft: isSelected ? "4px solid #10b981" : "4px solid transparent",
                                  transition: "all 0.15s ease",
                                }}
                                title="Nhấp để xem danh sách chi tiết các biển số này"
                              >
                                <td style={{ textAlign: "center" }}>
                                  {isSelected ? "👉 " : ""}{idx + 1}
                                </td>
                                <td>
                                  <strong>{r.don_vi || "—"}</strong>
                                </td>
                                <td>
                                  <span
                                    className={`badge ${
                                      r.tinh_trang?.includes("kho")
                                        ? "badge-warning"
                                        : r.tinh_trang === "Đã hủy"
                                        ? "badge-danger"
                                        : "badge-success"
                                    }`}
                                    style={{ fontWeight: 600 }}
                                  >
                                    {r.tinh_trang || r.phan_loai || "—"}
                                  </span>
                                </td>
                                <td>
                                  <StatusBadge status={r.giao || r.trang_thai} />
                                </td>
                                <td
                                  style={{
                                    textAlign: "right",
                                    fontWeight: 600,
                                    color: "#10b981",
                                  }}
                                >
                                  <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                                    <span>{(r.so_luong ?? 0).toLocaleString("vi-VN")}</span>
                                    <button
                                      type="button"
                                      className="btn btn-secondary"
                                      style={{
                                        padding: "2px 8px",
                                        fontSize: 11,
                                        height: 24,
                                        borderRadius: 4,
                                        background: isSelected ? "#10b981" : "#f1f5f9",
                                        color: isSelected ? "#fff" : "#047857",
                                        border: "1px solid #cbd5e1",
                                        cursor: "pointer",
                                      }}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleToggleBienRow(r);
                                      }}
                                    >
                                      {isSelected ? "Đang xem" : "Xem biển 🔍"}
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                      {filteredBangBien.length > 0 && (
                        <tfoot>
                          <tr style={{ background: "#f8fafc", fontWeight: 700 }}>
                            <td colSpan={4} style={{ textAlign: "right", paddingRight: 16 }}>
                              TỔNG SỐ BIỂN THEO TIẾN ĐỘ:
                            </td>
                            <td
                              style={{
                                textAlign: "right",
                                color: "#10b981",
                                fontSize: 14,
                              }}
                            >
                              {filteredBangBien
                                .reduce((acc: number, cur: any) => acc + (cur.so_luong || 0), 0)
                                .toLocaleString("vi-VN")}
                            </td>
                          </tr>
                        </tfoot>
                      )}
                    </table>
                  </div>
                </div>
              )}

              {/* Bảng R2 */}
              {reportCode === "R2" && (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: 60, textAlign: "center" }}>STT</th>
                      <th style={{ width: 80, textAlign: "center" }}>MÃ TỈNH</th>
                      <th style={{ width: 100, textAlign: "center" }}>MÃ XÃ</th>
                      <th>ĐƠN VỊ QUẢN LÝ</th>
                      <th>LOẠI PHƯƠNG TIỆN</th>
                      <th style={{ width: 100, textAlign: "center" }}>SERI CHỮ</th>
                      <th>TÌNH TRẠNG KHO</th>
                      <th style={{ width: 140, textAlign: "right" }}>SỐ LƯỢNG BIỂN</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.length === 0 ? (
                      <tr>
                        <td colSpan={8} style={{ textAlign: "center", padding: 24, color: "var(--color-text-muted)" }}>
                          Không có dữ liệu tồn kho phù hợp.
                        </td>
                      </tr>
                    ) : (
                      filteredRows.map((r: any, idx: number) => {
                        const isSelected = isR2RowSelected(r);
                        return (
                          <tr
                            key={idx}
                            onClick={() => handleToggleR2Row(r)}
                            style={{
                              cursor: "pointer",
                              background: isSelected ? "#fef3c7" : undefined,
                              borderLeft: isSelected ? "4px solid var(--color-warning)" : "4px solid transparent",
                              transition: "all 0.15s ease",
                            }}
                            title="Nhấp để xem danh sách chi tiết các biển số này"
                          >
                            <td style={{ textAlign: "center" }}>
                              {isSelected ? "👉 " : ""}{idx + 1}
                            </td>
                            <td style={{ textAlign: "center" }}>{r.tinh_ma}</td>
                            <td style={{ textAlign: "center" }}>{r.xa_ma || "—"}</td>
                            <td>
                              <strong>{r.don_vi || "—"}</strong>
                            </td>
                            <td>{r.loai_pt || "—"}</td>
                            <td style={{ textAlign: "center" }}>
                              <span className="badge" style={{ fontWeight: 700 }}>
                                {r.seri_chu || "—"}
                              </span>
                            </td>
                            <td>
                              <StatusBadge status={r.tinh_trang} />
                            </td>
                            <td style={{ textAlign: "right", fontWeight: 600 }}>
                              <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                                <span>{(r.so_bien ?? 0).toLocaleString("vi-VN")}</span>
                                <button
                                  type="button"
                                  className="btn btn-secondary"
                                  style={{
                                    padding: "2px 8px",
                                    fontSize: 11,
                                    height: 24,
                                    borderRadius: 4,
                                    background: isSelected ? "var(--color-warning)" : "#f1f5f9",
                                    color: isSelected ? "#fff" : "#b45309",
                                    border: "1px solid #cbd5e1",
                                    cursor: "pointer",
                                  }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleToggleR2Row(r);
                                  }}
                                >
                                  {isSelected ? "Đang xem" : "Xem biển 🔍"}
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                  {filteredRows.length > 0 && (
                    <tfoot>
                      <tr style={{ background: "#f8fafc", fontWeight: 700 }}>
                        <td colSpan={7} style={{ textAlign: "right", paddingRight: 16 }}>
                          TỔNG SỐ LƯỢNG BIỂN TỒN KHO:
                        </td>
                        <td style={{ textAlign: "right" }}>
                          {filteredRows
                            .reduce((acc: number, cur: any) => acc + (cur.so_bien || 0), 0)
                            .toLocaleString("vi-VN")}
                        </td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              )}

              {/* Bảng R3 */}
              {reportCode === "R3" && (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: 60, textAlign: "center" }}>STT</th>
                      <th style={{ width: 180 }}>GIAI ĐOẠN TIẾN ĐỘ</th>
                      <th>CÁC TRẠNG THÁI LÔ TƯƠNG ỨNG</th>
                      <th style={{ width: 140, textAlign: "right" }}>SỐ LÔ</th>
                      <th style={{ width: 140, textAlign: "right" }}>SỐ BIỂN</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.length === 0 ? (
                      <tr>
                        <td colSpan={5} style={{ textAlign: "center", padding: 24, color: "var(--color-text-muted)" }}>
                          Không có dữ liệu tiến độ.
                        </td>
                      </tr>
                    ) : (
                      filteredRows.map((r: any, idx: number) => (
                        <tr key={idx}>
                          <td style={{ textAlign: "center" }}>{idx + 1}</td>
                          <td>
                            <strong>{r.giai_doan}</strong>
                          </td>
                          <td>
                            <span style={{ color: "var(--color-text-muted)", fontSize: 13 }}>
                              {r.trang_thai_lo}
                            </span>
                          </td>
                          <td style={{ textAlign: "right", fontWeight: 600 }}>
                            {(r.so_lo ?? 0).toLocaleString("vi-VN")}
                          </td>
                          <td style={{ textAlign: "right", fontWeight: 600 }}>
                            {(r.so_bien ?? 0).toLocaleString("vi-VN")}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                  {filteredRows.length > 0 && (
                    <tfoot>
                      <tr style={{ background: "#f8fafc", fontWeight: 700 }}>
                        <td colSpan={3} style={{ textAlign: "right", paddingRight: 16 }}>
                          TỔNG CỘNG:
                        </td>
                        <td style={{ textAlign: "right" }}>
                          {filteredRows
                            .reduce((acc: number, cur: any) => acc + (cur.so_lo || 0), 0)
                            .toLocaleString("vi-VN")}
                        </td>
                        <td style={{ textAlign: "right" }}>
                          {filteredRows
                            .reduce((acc: number, cur: any) => acc + (cur.so_bien || 0), 0)
                            .toLocaleString("vi-VN")}
                        </td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              )}

              {/* Bảng R4 */}
              {reportCode === "R4" && (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: 60, textAlign: "center" }}>STT</th>
                      <th style={{ width: 80, textAlign: "center" }}>MÃ TỈNH</th>
                      <th style={{ width: 100, textAlign: "center" }}>MÃ XÃ</th>
                      <th>ĐƠN VỊ</th>
                      <th style={{ width: 130, textAlign: "right" }}>CHƯA TRẢ (TỒN)</th>
                      <th style={{ width: 130, textAlign: "right" }}>ĐÃ TRẢ (ĐÃ CẤP)</th>
                      <th style={{ width: 140, textAlign: "right" }}>THU HỒI VỀ XÃ</th>
                      <th style={{ width: 130, textAlign: "right" }}>TỔNG SỐ</th>
                      <th style={{ width: 120, textAlign: "right" }}>TỶ LỆ CẤP (%)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.length === 0 ? (
                      <tr>
                        <td colSpan={9} style={{ textAlign: "center", padding: 24, color: "var(--color-text-muted)" }}>
                          Không có dữ liệu cấp trả biển số.
                        </td>
                      </tr>
                    ) : (
                      filteredRows.map((r: any, idx: number) => {
                        const pct =
                          r.tong_so > 0 ? Math.round((r.da_tra / r.tong_so) * 100) : 0;
                        return (
                          <tr key={idx}>
                            <td style={{ textAlign: "center" }}>{idx + 1}</td>
                            <td style={{ textAlign: "center" }}>{r.tinh_ma}</td>
                            <td style={{ textAlign: "center" }}>{r.xa_ma || "—"}</td>
                            <td>
                              <strong>{r.don_vi || "—"}</strong>
                            </td>
                            <td style={{ textAlign: "right", color: "#0284c7", fontWeight: 600 }}>
                              {(r.chua_tra ?? 0).toLocaleString("vi-VN")}
                            </td>
                            <td style={{ textAlign: "right", color: "var(--color-success)", fontWeight: 600 }}>
                              {(r.da_tra ?? 0).toLocaleString("vi-VN")}
                            </td>
                            <td style={{ textAlign: "right", color: "var(--color-warning)", fontWeight: 600 }}>
                              {(r.thu_hoi_ve_xa ?? 0).toLocaleString("vi-VN")}
                            </td>
                            <td style={{ textAlign: "right", fontWeight: 700 }}>
                              {(r.tong_so ?? 0).toLocaleString("vi-VN")}
                            </td>
                            <td style={{ textAlign: "right" }}>
                              <span
                                style={{
                                  fontWeight: 700,
                                  color: pct >= 80 ? "var(--color-success)" : pct >= 40 ? "var(--color-warning)" : "inherit",
                                }}
                              >
                                {pct}%
                              </span>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                  {filteredRows.length > 0 && (
                    <tfoot>
                      <tr style={{ background: "#f8fafc", fontWeight: 700 }}>
                        <td colSpan={4} style={{ textAlign: "right", paddingRight: 16 }}>
                          TỔNG TOÀN ĐƠN VỊ:
                        </td>
                        <td style={{ textAlign: "right" }}>
                          {filteredRows
                            .reduce((acc: number, cur: any) => acc + (cur.chua_tra || 0), 0)
                            .toLocaleString("vi-VN")}
                        </td>
                        <td style={{ textAlign: "right" }}>
                          {filteredRows
                            .reduce((acc: number, cur: any) => acc + (cur.da_tra || 0), 0)
                            .toLocaleString("vi-VN")}
                        </td>
                        <td style={{ textAlign: "right" }}>
                          {filteredRows
                            .reduce((acc: number, cur: any) => acc + (cur.thu_hoi_ve_xa || 0), 0)
                            .toLocaleString("vi-VN")}
                        </td>
                        <td style={{ textAlign: "right" }}>
                          {filteredRows
                            .reduce((acc: number, cur: any) => acc + (cur.tong_so || 0), 0)
                            .toLocaleString("vi-VN")}
                        </td>
                        <td></td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              )}

              {/* Bảng R5 */}
              {reportCode === "R5" && (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: 60, textAlign: "center" }}>STT</th>
                      <th style={{ width: 140 }}>MÃ LÔ</th>
                      <th>ĐƠN VỊ</th>
                      <th>BIỂN SỐ ĐẦY ĐỦ</th>
                      <th>LOẠI PHƯƠNG TIỆN</th>
                      <th style={{ width: 100 }}>MÀU SẮC</th>
                      <th>TÌNH TRẠNG</th>
                      <th>TRẠNG THÁI GIAO</th>
                      <th>LÝ DO HỦY / THU HỒI</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.length === 0 ? (
                      <tr>
                        <td colSpan={9} style={{ textAlign: "center", padding: 24, color: "var(--color-text-muted)" }}>
                          Không có biển số bị hủy hoặc thu hồi trong phạm vi lọc.
                        </td>
                      </tr>
                    ) : (
                      filteredRows.map((r: any, idx: number) => (
                        <tr key={idx}>
                          <td style={{ textAlign: "center" }}>{idx + 1}</td>
                          <td>
                            <strong>{r.ma_lo}</strong>
                          </td>
                          <td>{r.don_vi || "—"}</td>
                          <td>
                            <strong style={{ fontSize: 14 }}>{r.bien_so_day_du}</strong>
                          </td>
                          <td>{r.loai_pt || "—"}</td>
                          <td>{r.mau_sac || "—"}</td>
                          <td>
                            <StatusBadge status={r.tinh_trang} />
                          </td>
                          <td>
                            <StatusBadge status={r.giao} />
                          </td>
                          <td style={{ color: "var(--color-danger)", fontWeight: 500 }}>
                            {r.ly_do || "—"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                  {filteredRows.length > 0 && (
                    <tfoot>
                      <tr style={{ background: "#f8fafc", fontWeight: 700 }}>
                        <td colSpan={8} style={{ textAlign: "right", paddingRight: 16 }}>
                          TỔNG SỐ LƯỢNG BIỂN ĐÃ HỦY / THU HỒI:
                        </td>
                        <td style={{ color: "var(--color-danger)" }}>
                          {filteredRows.length.toLocaleString("vi-VN")}
                        </td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              )}
            </div>

            {/* Khối hiển thị chi tiết Biển số tương tác (Drill-down) */}
            {selectedDrilldown && (
              <div
                ref={drilldownRef}
                style={{
                  marginTop: 20,
                  padding: 18,
                  border: "2px solid var(--color-primary)",
                  borderRadius: "var(--radius-md)",
                  boxShadow: "0 8px 24px rgba(27, 54, 93, 0.12)",
                  background: "#ffffff",
                }}
              >
                {/* Header drilldown */}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    flexWrap: "wrap",
                    gap: 12,
                    paddingBottom: 12,
                    marginBottom: 12,
                    borderBottom: "1px solid var(--color-border)",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <span
                        className={`badge ${selectedDrilldown.badgeClass}`}
                        style={{ fontWeight: 700, fontSize: 12 }}
                      >
                        {selectedDrilldown.tableType === "LO"
                          ? "CHI TIẾT THEO LÔ"
                          : selectedDrilldown.tableType === "BIEN"
                          ? "CHI TIẾT THEO BIỂN"
                          : "CHI TIẾT BIỂN SỐ"}
                      </span>
                      <h4 style={{ margin: 0, fontSize: 16, color: "var(--color-primary)" }}>
                        {selectedDrilldown.title}
                      </h4>
                    </div>
                    <div style={{ fontSize: 13, color: "var(--color-text-muted)" }}>
                      Đơn vị: <strong>{selectedDrilldown.unitName}</strong> • {selectedDrilldown.badgeText} •{" "}
                      <strong style={{ color: "var(--color-primary)" }}>
                        {drilldownPlates.length}
                      </strong>{" "}
                      biển số tương ứng
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <input
                      className="input"
                      placeholder="Lọc biển số trong danh sách..."
                      style={{ width: 220 }}
                      value={drilldownSearch}
                      onChange={(e) => setDrilldownSearch(e.target.value)}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => {
                        setSelectedDrilldown(null);
                        setDrilldownPlates([]);
                      }}
                      style={{ padding: "6px 14px", fontSize: 13 }}
                    >
                      ✖ Đóng chi tiết
                    </button>
                  </div>
                </div>

                {/* Nội dung danh sách biển số */}
                {loadingDrilldown ? (
                  <div style={{ textAlign: "center", padding: 32, color: "var(--color-text-muted)" }}>
                    Đang tải danh sách biển số chi tiết...
                  </div>
                ) : filteredDrilldownPlates.length === 0 ? (
                  <div style={{ textAlign: "center", padding: 24, color: "var(--color-text-muted)" }}>
                    {drilldownSearch
                      ? "Không tìm thấy biển số nào khớp với từ khóa tìm kiếm."
                      : "Không có biển số nào thuộc phân nhóm này."}
                  </div>
                ) : (
                  <div style={{ overflowX: "auto", maxHeight: 420 }}>
                    <table className="data-table" style={{ fontSize: 13 }}>
                      <thead style={{ position: "sticky", top: 0, zIndex: 1, background: "#f8fafc" }}>
                        <tr>
                          <th style={{ width: 50, textAlign: "center" }}>STT</th>
                          <th style={{ width: 140 }}>MÃ LÔ</th>
                          <th style={{ width: 140 }}>MÃ LÔ ĐNM</th>
                          <th style={{ minWidth: 160 }}>ĐƠN VỊ</th>
                          <th style={{ width: 140 }}>BIỂN SỐ</th>
                          <th style={{ minWidth: 160 }}>LOẠI PHƯƠNG TIỆN</th>
                          <th style={{ width: 100, textAlign: "center" }}>MÀU SẮC</th>
                          <th style={{ width: 130 }}>TÌNH TRẠNG KHO</th>
                          <th style={{ width: 130 }}>TRẠNG THÁI GIAO</th>
                          <th style={{ width: 130 }}>NGÀY TẠO</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredDrilldownPlates.map((p: any, pIdx: number) => (
                          <tr key={p.id || pIdx}>
                            <td style={{ textAlign: "center" }}>{pIdx + 1}</td>
                            <td>
                              <strong>{p.ma_lo || "—"}</strong>
                            </td>
                            <td>{p.ma_lo_dnm ? <strong>{p.ma_lo_dnm}</strong> : "—"}</td>
                            <td>{p.don_vi || "—"}</td>
                            <td>
                              <span
                                style={{
                                  fontFamily: "monospace",
                                  fontWeight: 700,
                                  fontSize: 14,
                                  color: "#0f172a",
                                  background: "#f1f5f9",
                                  padding: "2px 6px",
                                  borderRadius: 4,
                                  border: "1px solid #cbd5e1",
                                }}
                              >
                                {p.bien_so_day_du}
                              </span>
                            </td>
                            <td>{p.loai_pt || "—"}</td>
                            <td style={{ textAlign: "center" }}>
                              <span
                                className={`badge ${
                                  p.mau_sac === "VÀNG"
                                    ? "badge-warning"
                                    : p.mau_sac === "XANH"
                                    ? "badge-info"
                                    : "badge-secondary"
                                }`}
                              >
                                {p.mau_sac || "TRẮNG"}
                              </span>
                            </td>
                            <td>
                              <StatusBadge status={p.tinh_trang} />
                            </td>
                            <td>
                              <StatusBadge status={p.giao} />
                            </td>
                            <td style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
                              {p.tao_luc || "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr style={{ background: "#f8fafc", fontWeight: 700 }}>
                          <td colSpan={4} style={{ textAlign: "right", paddingRight: 16 }}>
                            TỔNG SỐ BIỂN HIỂN THỊ:
                          </td>
                          <td colSpan={6} style={{ color: "var(--color-primary)" }}>
                            {filteredDrilldownPlates.length.toLocaleString("vi-VN")} biển số
                          </td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
