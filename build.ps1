# Сборка одним скриптом (нужен Windows + Python 3.10–3.11, 64 бита).
# Результат: dist\bomjvoice.exe и dist_installer\bomjvoice-Setup.exe
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    $ok = $false
    try { py -3.11 -m venv .venv *> $null; $ok = ($LASTEXITCODE -eq 0) } catch { $ok = $false }
    if (-not $ok) { python -m venv .venv }
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\pip.exe install -r requirements-dev.txt
# Необязательно: для клонирования голоса. Раскомментируйте для сборки с XTTS:
# .\.venv\Scripts\pip.exe install -r requirements-optional.txt

.\.venv\Scripts\pyinstaller.exe --noconfirm --clean bomjvoice.spec

if (Get-Command iscc -ErrorAction SilentlyContinue) {
    iscc installer\install.iss
    Write-Host "Готово: dist_installer\bomjvoice-Setup.exe"
} else {
    Write-Host "Inno Setup не найден (iscc). Установите Inno Setup — или отдайте папку dist\bomjvoice как есть."
}

