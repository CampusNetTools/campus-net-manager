param(
    [Parameter(Mandatory = $true)]
    [string]$ExecutablePath,
    [string]$ReportPath = "dist/windows/windows-ui-acceptance.txt",
    [string]$ScreenshotPrefix = "dist/windows/windows-ui-wizard",
    [switch]$RunPersistenceProbe
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing.Common

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class CampusNetUiWindow {
    [StructLayout(LayoutKind.Sequential)]
    public struct Rect { public int Left; public int Top; public int Right; public int Bottom; }
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr handle, int command);
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr handle);
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr handle, out Rect rect);
    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")]
    public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extraInfo);
}
"@

$report = [System.Collections.Generic.List[string]]::new()
$process = $null
$probeConfigPath = $null
$probeProfileName = "Codex VM acceptance"
$probeConfigSeeded = $false

function Add-Report([string]$Line) {
    $report.Add($Line)
    Write-Output $Line
}

function Get-ProcessWindows([int]$ProcessId) {
    $condition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ProcessIdProperty,
        $ProcessId
    )
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    # Tk Toplevel dialogs created with transient(root) may appear as owned
    # descendants instead of direct desktop children in the UIA tree.
    foreach ($window in $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)) {
        if (-not $window.Current.IsOffscreen) {
            $window
        }
    }
}

function Get-ApplicationProcessIds([int]$RootProcessId) {
    # PyInstaller one-file executables can keep a bootloader parent alive while
    # the actual Python/Tk UI runs in a child process. UI Automation reports the
    # child PID, so searching only Start-Process.Id misses the real window.
    $processes = @(Get-CimInstance -ClassName Win32_Process)
    $ids = [System.Collections.Generic.HashSet[int]]::new()
    [void]$ids.Add($RootProcessId)
    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($candidate in $processes) {
            if ($ids.Contains([int]$candidate.ParentProcessId) -and
                $ids.Add([int]$candidate.ProcessId)) {
                $changed = $true
            }
        }
    }
    @($ids)
}

function Capture-WindowScreenshot([IntPtr]$Handle, [string]$Path) {
    $rect = [CampusNetUiWindow+Rect]::new()
    if (-not [CampusNetUiWindow]::GetWindowRect($Handle, [ref]$rect)) {
        throw "Could not read window bounds before screenshot capture."
    }
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    if ($width -le 0 -or $height -le 0) {
        throw "Invalid screenshot bounds: $($rect.Left),$($rect.Top),$($rect.Right),$($rect.Bottom)."
    }
    $bitmap = [System.Drawing.Bitmap]::new($width, $height)
    try {
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        try {
            $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bitmap.Size)
            $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
        }
        finally {
            $graphics.Dispose()
        }
    }
    finally {
        $bitmap.Dispose()
    }
    "${Path}|$($rect.Left),$($rect.Top),$($rect.Right),$($rect.Bottom)|${width}x${height}"
}

function Wait-ProcessWindow([int]$RootProcessId, [scriptblock]$Predicate, [string]$Description) {
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    $refreshAt = [DateTime]::MinValue
    $processIds = @($RootProcessId)
    do {
        if ([DateTime]::UtcNow -ge $refreshAt) {
            $processIds = @(Get-ApplicationProcessIds -RootProcessId $RootProcessId)
            $refreshAt = [DateTime]::UtcNow.AddSeconds(1)
        }
        foreach ($processId in $processIds) {
            foreach ($window in Get-ProcessWindows -ProcessId $processId) {
                if (& $Predicate $window) {
                    return $window
                }
            }
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    $visibleNames = @(
        foreach ($processId in $processIds) {
            foreach ($window in Get-ProcessWindows -ProcessId $processId) {
                if ($window.Current.Name) { $window.Current.Name }
            }
        }
    ) | Select-Object -Unique
    throw "Timed out waiting for visible UI window: $Description (process IDs: $($processIds -join ','); visible window names: $($visibleNames -join ' | '))."
}

function Assert-PersistedProbeConfig([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Persistence probe config was not written: $Path"
    }
    try {
        $config = Get-Content -LiteralPath $Path -Raw -Encoding utf8 | ConvertFrom-Json
    }
    catch {
        throw "Persistence probe config is not valid JSON."
    }
    if ($config.active_profile -ne $probeProfileName -or
        $config.auto_update_check -ne $false) {
        throw "Persistence probe profile or local-only setting was not preserved."
    }
    $profiles = @($config.profiles | Where-Object { $_.name -eq $probeProfileName })
    if ($profiles.Count -ne 1 -or $profiles[0].auth_url -ne "http://127.0.0.1:9/" -or
        $profiles[0].username -or $profiles[0].password) {
        throw "Persistence probe profile is missing, altered, or contains credential values."
    }
}

function Stop-ApplicationProcessTree([int]$RootProcessId) {
    $remainingIds = @(Get-ApplicationProcessIds -RootProcessId $RootProcessId)
    foreach ($remainingId in $remainingIds | Where-Object { $_ -ne $RootProcessId }) {
        Stop-Process -Id $remainingId -Force -ErrorAction SilentlyContinue
    }
    Stop-Process -Id $RootProcessId -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}

function Click-WizardPlanA($Window) {
    $handle = [IntPtr]$Window.Current.NativeWindowHandle
    if ($handle -eq [IntPtr]::Zero) {
        throw "No native window handle for the first-run wizard."
    }
    [void][CampusNetUiWindow]::ShowWindow($handle, 9)
    if (-not [CampusNetUiWindow]::SetForegroundWindow($handle)) {
        throw "Could not activate the first-run wizard window."
    }
    $rect = [CampusNetUiWindow+Rect]::new()
    if (-not [CampusNetUiWindow]::GetWindowRect($handle, [ref]$rect)) {
        throw "Could not get the first-run wizard window bounds."
    }
    Add-Report "wizard_window_bounds=$($rect.Left),$($rect.Top),$($rect.Right),$($rect.Bottom)"
    Add-Report "wizard_window_size=$($rect.Right - $rect.Left)x$($rect.Bottom - $rect.Top)"
    $beforePath = "${ScreenshotPrefix}-before.png"
    Add-Report "wizard_screenshot_before=$(Capture-WindowScreenshot -Handle $handle -Path $beforePath)"
    # In the choice screen, plan A is the rightmost bottom button. Click its
    # interior using window bounds; do not click any controls on the plan page.
    $x = $rect.Right - 70
    $y = $rect.Bottom - 58
    if (-not [CampusNetUiWindow]::SetCursorPos($x, $y)) {
        throw "Could not move the VM pointer to the plan A choice."
    }
    Start-Sleep -Milliseconds 150
    [CampusNetUiWindow]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 80
    [CampusNetUiWindow]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
    Add-Report "plan_a_button_click=absolute screen position derived from wizard bounds ($x,$y)"
    # Let Tk process the explicit idle/layout flush before capturing the page.
    Start-Sleep -Milliseconds 1500
    $afterPath = "${ScreenshotPrefix}-after.png"
    Add-Report "wizard_screenshot_after=$(Capture-WindowScreenshot -Handle $handle -Path $afterPath)"
}

try {
    $resolvedExe = (Resolve-Path -LiteralPath $ExecutablePath).Path
    $reportDirectory = Split-Path -Parent $ReportPath
    if ($reportDirectory) {
        New-Item -ItemType Directory -Force -Path $reportDirectory | Out-Null
    }
    Add-Report "result=started"
    Add-Report "environment=GitHub-hosted Windows x64 VM"
    Add-Report "os=$([Environment]::OSVersion.VersionString)"
    Add-Report "executable=$([IO.Path]::GetFileName($resolvedExe))"

    if ($RunPersistenceProbe) {
        $probeConfigPath = Join-Path (Split-Path -Parent $resolvedExe) "config.json"
        if (Test-Path -LiteralPath $probeConfigPath) {
            throw "The isolated executable directory already contains config.json."
        }
        $seed = @{
            profiles = @(@{
                name = $probeProfileName
                profile_type = "campus"
                ssid = ""
                username = ""
                password = ""
                login_type = "cmcc"
                auth_url = "http://127.0.0.1:9/"
                interval = 60
            })
            active_profile = $probeProfileName
            auth_history = @("http://127.0.0.1:9/")
            auto_update_check = $false
            notifications = @{ enabled = $true }
        }
        $json = $seed | ConvertTo-Json -Depth 8 -Compress
        [IO.File]::WriteAllText($probeConfigPath, $json, [Text.UTF8Encoding]::new($false))
        $probeConfigSeeded = $true
        Add-Report "persistence_probe=isolated empty profile with loopback-only auth endpoint"
    }

    $process = Start-Process -FilePath $resolvedExe `
        -WorkingDirectory (Split-Path -Parent $resolvedExe) -PassThru
    Add-Report "root_process_id=$($process.Id)"
    Add-Report "root_process_session_id=$($process.SessionId)"

    $mainWindow = Wait-ProcessWindow -RootProcessId $process.Id -Description "main window" -Predicate {
        param($window)
        $window.Current.Name.Contains("校园网连接管家")
    }
    Add-Report "main_window=visible"
    Add-Report "main_window_process_id=$($mainWindow.Current.ProcessId)"

    # With an isolated runner profile and no enrolled campus credentials, the
    # first-run wizard is shown automatically. We only exercise its local text
    # navigation and deliberately never invoke network/settings buttons.
    $wizard = Wait-ProcessWindow -RootProcessId $process.Id -Description "first-run wizard" -Predicate {
        param($window)
        $window.Current.Name -eq "新手向导"
    }
    Add-Report "first_run_wizard=visible"
    if ($RunPersistenceProbe) {
        Assert-PersistedProbeConfig -Path $probeConfigPath
        Add-Report "config_after_app_load=valid JSON, synthetic profile and local-only setting preserved"
    }

    # Tk buttons are not represented as UIA controls on this hosted runner.
    # Use a bounded click on plan A's visible button and verify the new title.
    Click-WizardPlanA -Window $wizard
    $planA = Wait-ProcessWindow -RootProcessId $process.Id -Description "plan A wizard view" -Predicate {
        param($window)
        $window.Current.Name.StartsWith("方式 A")
    }
    Add-Report "plan_a_view=visible"
    Add-Report "network_settings_actions=not_invoked"
    Add-Report "hotspot_and_wifi_actions=not_invoked"
    if ($RunPersistenceProbe) {
        Stop-ApplicationProcessTree -RootProcessId $process.Id
        $process = $null
        $process = Start-Process -FilePath $resolvedExe `
            -WorkingDirectory (Split-Path -Parent $resolvedExe) -PassThru
        Add-Report "restart_root_process_id=$($process.Id)"
        $restartWindow = Wait-ProcessWindow -RootProcessId $process.Id -Description "main window after config restart" -Predicate {
            param($window)
            $window.Current.Name.Contains("校园网连接管家")
        }
        Add-Report "main_window_after_config_restart=visible"
        Assert-PersistedProbeConfig -Path $probeConfigPath
        Add-Report "config_survives_process_restart=valid JSON, synthetic profile and local-only setting preserved"
    }
    # On the A page, Tab focuses the hotspot action first. Do not send another
    # Space or Tab sequence: that could open Windows network settings.
    Add-Report "result=passed"
}
catch {
    Add-Report "result=failed"
    Add-Report "error=$($_.Exception.Message)"
    throw
}
finally {
    if ($process) {
        # Also stop a surviving PyInstaller child if its bootloader parent has
        # already exited after spawning the GUI process.
        Stop-ApplicationProcessTree -RootProcessId $process.Id
        Add-Report "process_cleanup=stopped"
    }
    if ($probeConfigSeeded -and $probeConfigPath) {
        $probeDirectory = Split-Path -Parent $probeConfigPath
        foreach ($generatedPath in @(
            $probeConfigPath,
            "$probeConfigPath.tmp",
            (Join-Path $probeDirectory "keepalive.log"),
            (Join-Path $probeDirectory "keepalive.lock"),
            (Join-Path $probeDirectory "app.instance.lock"),
            (Join-Path $probeDirectory "network_history.jsonl")
        )) {
            if (Test-Path -LiteralPath $generatedPath -PathType Leaf) {
                Remove-Item -LiteralPath $generatedPath -Force
            }
        }
        Add-Report "persistence_probe_cleanup=isolated test files removed"
    }
    $report | Set-Content -LiteralPath $ReportPath -Encoding utf8
}
