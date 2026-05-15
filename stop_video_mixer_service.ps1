$ErrorActionPreference = "SilentlyContinue"
$stopped = New-Object System.Collections.Generic.List[string]
$connections = Get-NetTCPConnection -LocalPort 8787 | Where-Object { $_.OwningProcess -ne 0 }
foreach ($connection in $connections) {
    $proc = Get-Process -Id $connection.OwningProcess
    if ($proc -and ($proc.ProcessName -like "python*" -or $proc.ProcessName -eq "VideoMixerUI" -or $proc.ProcessName -eq "VideoMixerUI_Debug")) {
        $stopped.Add("$($proc.ProcessName)($($proc.Id))")
        Stop-Process -Id $proc.Id -Force
    }
}
Get-Process VideoMixerUI,VideoMixerUI_Debug | ForEach-Object {
    $stopped.Add("$($_.ProcessName)($($_.Id))")
    Stop-Process -Id $_.Id -Force
}
Start-Sleep -Seconds 1
$listening = Get-NetTCPConnection -LocalPort 8787 | Where-Object { $_.State -eq "Listen" -and $_.OwningProcess -ne 0 }
Write-Host ""
if ($stopped.Count -gt 0) { Write-Host "Stopped: $($stopped -join ', ')" } else { Write-Host "No running VideoMixerUI service was found." }
if ($listening) { Write-Host "Port 8787 is still listening. Please close the process manually from Task Manager." } else { Write-Host "Port 8787 is free. Service is closed." }
Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
