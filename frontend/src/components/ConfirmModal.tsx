import { ReactNode } from "react";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmModal({
  open,
  title,
  children,
  confirmLabel = "Xác nhận",
  cancelLabel = "Hủy bỏ",
  danger = false,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  if (!open) return null;
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-box">
        <h3 style={{ marginTop: 0 }}>{title}</h3>
        <div style={{ marginBottom: 16 }}>{children}</div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button type="button" className="btn btn-secondary" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={`btn ${danger ? "btn-danger" : ""}`}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export function StatusBadge({ status }: { status?: string | null }) {
  if (!status) return <span>—</span>;
  let cls = "badge";
  if (
    ["Chấp nhận", "Đặt thành công", "Đã nhập kho", "Đã nhận", "Đã chuyển Xã/phường", "Đã trả", "Tồn kho xã", "Tồn kho tỉnh"].includes(
      status
    )
  ) {
    cls += " badge-success";
  } else if (
    ["Chờ phê duyệt", "Đã gửi", "Cho phép điều chỉnh", "Đã đặt", "Chưa trả"].includes(
      status
    )
  ) {
    cls += " badge-warning";
  } else if (["Từ chối", "Hủy", "Đã hủy", "Thu hồi về xã"].includes(status)) {
    cls += " badge-danger";
  }
  return <span className={cls}>{status}</span>;
}
