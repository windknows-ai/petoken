param([string]$Script, [int]$Timeout = 900)
$sf = "D:\Program Files\Adobe After Effects 2022\Support Files"
$p = Start-Process -FilePath "$sf\AfterFX.exe" -ArgumentList '-noui', '-r', $Script -WorkingDirectory $sf -PassThru
if (-not $p.WaitForExit($Timeout * 1000)) { Stop-Process -Id $p.Id -Force; "timeout" } else { "exit $($p.ExitCode)" }
