param(
    [string]$Database = "biensoxe_dev",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 5432,
    [string]$User = "postgres",
    [string]$BackupDir = "$PSScriptRoot\backups",
    [int]$RetentionDays = 30
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

$PgBin = "c:\Users\xitos\Projects\_tools\pgsql\bin"
$PgDump = if (Test-Path "$PgBin\pg_dump.exe") { "$PgBin\pg_dump.exe" } else { "pg_dump" }
$PgRestore = if (Test-Path "$PgBin\pg_restore.exe") { "$PgBin\pg_restore.exe" } else { "pg_restore" }

$Timestamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
$DumpFile = Join-Path $BackupDir "${Database}_${Timestamp}.dump"

Write-Host "[1/3] Sao lưu cơ sở dữ liệu '$Database' ra '$DumpFile'..."
& $PgDump -h $HostName -p $Port -U $User -Fc -f $DumpFile $Database
if ($LASTEXITCODE -ne 0) {
    throw "pg_dump thất bại với mã lỗi $LASTEXITCODE"
}

Write-Host "[2/3] Kiểm tra toàn vẹn bản sao lưu bằng pg_restore --list..."
$ManifestCount = (& $PgRestore --list $DumpFile | Measure-Object -Line).Lines
if ($LASTEXITCODE -ne 0 -or $ManifestCount -lt 10) {
    throw "Kiểm tra toàn vẹn bản sao lưu thất bại!"
}
Write-Host "Bản sao lưu hợp lệ ($ManifestCount mục trong danh sách TOC)."

Write-Host "[3/3] Dọn các bản sao lưu cũ hơn $RetentionDays ngày (NFR-006)..."
$Cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem -Path $BackupDir -Filter "*.dump" | Where-Object { $_.LastWriteTime -lt $Cutoff } | Remove-Item -Force

Write-Output $DumpFile

