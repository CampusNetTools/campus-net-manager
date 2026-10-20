param(
    [Parameter(Mandatory = $true)]
    [string]$ExecutablePath,
    [string]$ReportPath = "dist/windows/windows-ui-acceptance.txt"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class CampusNetUiWindow {
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr handle, int command);
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr handle);
}
"@

$report = [System.Collections.Generic.List[string]]::new()
$process = $null

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
    throw "Timed out waiting for visible UI window: $Description (process IDs: $($processIds -join ','))."
}

function Send-KeyboardToWindow($Window, [string]$Keys, [string]$Description) {
    $handle = [IntPtr]$Window.Current.NativeWindowHandle
    if ($handle -eq [IntPtr]::Zero) {
        throw "No native window handle for keyboard navigation: $Description."
    }
    [void][CampusNetUiWindow]::ShowWindow($handle, 9)
    if (-not [CampusNetUiWindow]::SetForegroundWindow($handle)) {
        throw "Could not activate the wizard window for keyboard navigation: $Description."
    }
    Start-Sleep -Milliseconds 300
    [System.Windows.Forms.SendKeys]::SendWait($Keys)
    Add-Report "keyboard_navigation=$Description"
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

    # Tk buttons are visible but may not be represented as UIA button controls
    # on hosted Windows runners. Use the normal keyboard focus order instead.
    Send-KeyboardToWindow -Window $wizard -Keys "{TAB}{SPACE}" `
        -Description "select first wizard option with Tab and Space"
    $planA = Wait-ProcessWindow -RootProcessId $process.Id -Description "plan A wizard view" -Predicate {
        param($window)
        $window.Current.Name -eq "方式 A：电脑直连校园网"
    }
    Add-Report "plan_a_view=visible"
    Add-Report "network_settings_actions=not_invoked"
    Add-Report "hotspot_and_wifi_actions=not_invoked"
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
        $remainingIds = @(Get-ApplicationProcessIds -RootProcessId $process.Id)
        foreach ($remainingId in $remainingIds | Where-Object { $_ -ne $process.Id }) {
            Stop-Process -Id $remainingId -Force -ErrorAction SilentlyContinue
        }
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
        Add-Report "process_cleanup=stopped"
    }
    $report | Set-Content -LiteralPath $ReportPath -Encoding utf8
}
