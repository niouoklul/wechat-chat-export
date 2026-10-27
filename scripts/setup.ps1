param()
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$base = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $env:TEMP }
if (-not $base) { throw '未找到本机用户缓存目录。' }
$venv = Join-Path $base 'wechat-chat-export\venv312'
$py = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $py -PathType Leaf)) {
    $candidates = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $candidates += ,@('py', '-3.12')
    }
    if (Get-Command python -ErrorAction SilentlyContinue) { $candidates += ,@('python') }
    $selected = $null
    foreach ($candidate in $candidates) {
        $exe = $candidate[0]
        $flags = @($candidate | Select-Object -Skip 1)
        try { $v = & $exe @flags -c 'import struct,sys; print(sys.version_info[:2] in ((3,12),) and struct.calcsize(chr(80))==8)' 2>$null } catch { continue }
        if ($LASTEXITCODE -eq 0 -and ($v | Select-Object -Last 1) -eq 'True') { $selected = $candidate; break }
    }
    if (-not $selected) { throw '请先安装 64 位 Python 3.12（含 venv 和 pip）。' }
    $exe = $selected[0]
    $flags = @($selected | Select-Object -Skip 1)
    & $exe @flags -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw '创建独立 Python 环境失败。' }
}
& $py -m pip install --disable-pip-version-check --no-input --quiet -r (Join-Path $root 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw '安装 Python 依赖失败；没有读取微信数据。' }
$hash = (Get-FileHash -LiteralPath (Join-Path $root 'requirements.txt') -Algorithm SHA256).Hash
Set-Content -LiteralPath (Join-Path $venv 'skill-ready.txt') -Value $hash -Encoding ascii
Write-Output "依赖已安装到 $venv"
