/**
 * Định dạng ngày giờ theo chuẩn dd/MM/yyyy HH:mm ở múi giờ UTC+7 (NFR-012).
 */
export function formatDateTimeVN(isoOrDate: string | Date | null | undefined): string {
  if (!isoOrDate) return "";
  const date = typeof isoOrDate === "string" ? new Date(isoOrDate) : isoOrDate;
  if (Number.isNaN(date.getTime())) return "";
  const formatter = new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const parts = formatter.formatToParts(date);
  const map: Record<string, string> = {};
  for (const part of parts) {
    map[part.type] = part.value;
  }
  return `${map.day}/${map.month}/${map.year} ${map.hour}:${map.minute}`;
}

