import { useEffect, useState } from "react";
import { apiRequest } from "../../api/client";

export function BaoCaoPage() {
  const [reportCode, setReportCode] = useState<"R1" | "R2" | "R3" | "R4" | "R5">(
    "R1"
  );
  const [tinhMa, setTinhMa] = useState("");
  const [xaMa, setXaMa] = useState("");
  const [data, setData] = useState<any>(null);

  const buildQs = () => {
    const p = new URLSearchParams();
    if (tinhMa.trim()) p.set("tinh_ma", tinhMa.trim());
    if (xaMa.trim()) p.set("xa_ma", xaMa.trim());
    return p.toString();
  };

  const loadReport = async () => {
    const qs = buildQs();
    const res = await apiRequest(
      `/api/v1/bao-cao/${reportCode}${qs ? `?${qs}` : ""}`
    );
    setData(res);
  };

  useEffect(() => {
    void loadReport();
  }, [reportCode]);

  const exportUrl = `/api/v1/bao-cao/${reportCode}/xuat?${buildQs()}`;

  return (
    <div>
      <h2>Báo cáo Thống kê R1–R5 & Xuất Excel (FR-080, FR-081)</h2>
      <div className="card">
        <div className="toolbar">
          {(["R1", "R2", "R3", "R4", "R5"] as const).map((c) => (
            <button
              key={c}
              type="button"
              className={`btn ${reportCode === c ? "" : "btn-secondary"}`}
              onClick={() => setReportCode(c)}
            >
              {c}
            </button>
          ))}
          <input
            className="input"
            placeholder="Mã tỉnh (VD: 01)"
            value={tinhMa}
            onChange={(e) => setTinhMa(e.target.value)}
          />
          <input
            className="input"
            placeholder="Mã xã"
            value={xaMa}
            onChange={(e) => setXaMa(e.target.value)}
          />
          <button
            type="button"
            className="btn"
            onClick={() => void loadReport()}
          >
            Xem báo cáo
          </button>
          <a href={exportUrl} className="btn btn-secondary">
            Xuất Excel (.xlsx)
          </a>
        </div>

        {data && (
          <div>
            <h3>{data.title}</h3>
            <table className="data-table">
              <thead>
                <tr>
                  <th>STT</th>
                  {data.rows?.[0] &&
                    Object.keys(data.rows[0]).map((k) => (
                      <th key={k}>{k.toUpperCase()}</th>
                    ))}
                </tr>
              </thead>
              <tbody>
                {(data.rows || []).map((r: any, idx: number) => (
                  <tr key={idx}>
                    <td>{idx + 1}</td>
                    {Object.keys(r).map((k) => (
                      <td key={k}>{String(r[k] ?? "—")}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
