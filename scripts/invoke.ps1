param([Parameter(ValueFromRemainingArguments=$true)][string[]]$SkillArguments)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$root = Split-Path -Parent $PSScriptRoot
$base = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $env:TEMP }
if (-not $base) { throw '未找到本机用户缓存目录。' }
$venv = Join-Path $base 'wechat-chat-export\venv312'
$py = Join-Path $venv 'Scripts\python.exe'
$marker = Join-Path $venv 'skill-ready.txt'
$expected = (Get-FileHash -LiteralPath (Join-Path $root 'requirements.txt') -Algorithm SHA256).Hash
if (-not (Test-Path -LiteralPath $py -PathType Leaf) -or
    -not (Test-Path -LiteralPath $marker -PathType Leaf) -or
    (Get-Content -LiteralPath $marker -Raw).Trim() -ne $expected) {
    & (Join-Path $PSScriptRoot 'setup.ps1')
}
if (-not (Test-Path -LiteralPath $marker -PathType Leaf) -or
    (Get-Content -LiteralPath $marker -Raw).Trim() -ne $expected) { throw '技能依赖未安装。' }
if ($SkillArguments.Count -eq 1 -and $SkillArguments[0] -eq 'doctor') {
    & $py -B -I -X utf8 (Join-Path $PSScriptRoot 'doctor.py')
} elseif ($SkillArguments.Count -gt 0 -and $SkillArguments[0] -eq 'list') {
    & $py -B -I -X utf8 (Join-Path $PSScriptRoot 'list_chats.py') @($SkillArguments | Select-Object -Skip 1)
} elseif ($SkillArguments.Count -gt 0 -and $SkillArguments[0] -eq 'export') {
    & $py -B -I -X utf8 (Join-Path $PSScriptRoot 'export_one.py') @($SkillArguments | Select-Object -Skip 1)
} else { throw '用法：invoke.ps1 doctor/list，或 invoke.ps1 export --name ... --output-base ... --confirm 确认导出' }
exit $LASTEXITCODE