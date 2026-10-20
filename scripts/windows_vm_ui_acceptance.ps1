param(
    [Parameter(Mandatory = $true)]
    [string]$ExecutablePath,
    [string]$ReportPath = "dist/windows/windows-ui-acceptance.txt"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

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
    foreach ($window in $root.FindAll([System.Windows.Automation.TreeScope]::Children, $condition)) {
        if (-not $window.Current.IsOffscreen) {
            $window
        }
    }
}

function Wait-ProcessWindow([int]$ProcessId, [scriptblock]$Predicate, [string]$Description) {
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    do {
        foreach ($window in Get-ProcessWindows -ProcessId $ProcessId) {
            if (& $Predicate $window) {
                return $window
            }
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "Timed out waiting for visible UI window: $Description"
}

function Get-Buttons($Window) {
    $all = $Window.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.Condition]::TrueCondition
    )
    foreach ($element in $all) {
        if ($element.Current.ControlType -eq [System.Windows.Automation.ControlType]::Button -and
            -not [string]::IsNullOrWhiteSpace($element.Current.Name)) {
            $element
        }
    }
}

function Invoke-ButtonByName($Window, [string]$Name) {
    foreach ($button in Get-Buttons -Window $Window) {
        if ($button.Current.Name -eq $Name) {
            $pattern = $null
            if ($button.TryGetCurrentPattern(
                    [System.Windows.Automation.InvokePattern]::Pattern,
                    [ref]$pattern)) {
                $pattern.Invoke()
                return
            }
            throw "UI button '$Name' does not expose InvokePattern."
        }
    }
    throw "Expected UI button '$Name' was not found."
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

    $mainWindow = Wait-ProcessWindow -ProcessId $process.Id -Description "main window" -Predicate {
        param($window)
        $window.Current.Name.Contains("校园网连接管家")
    }
    Add-Report "main_window=visible"

    # With an isolated runner profile and no enrolled campus credentials, the
    # first-run wizard is shown automatically. We only exercise its local text
    # navigation and deliberately never invoke network/settings buttons.
    $wizard = Wait-ProcessWindow -ProcessId $process.Id -Description "first-run wizard" -Predicate {
        param($window)
        $window.Current.Name -eq "新手向导"
    }
    Add-Report "first_run_wizard=visible"

    Invoke-ButtonByName -Window $wizard -Name "A：电脑直连"
    $planA = Wait-ProcessWindow -ProcessId $process.Id -Description "plan A wizard view" -Predicate {
        param($window)
        $window.Current.Name -eq "方式 A：电脑直连校园网"
    }
    $planAButtons = @(Get-Buttons -Window $planA | ForEach-Object { $_.Current.Name })
    if ($planAButtons -notcontains "打开 WiFi 设置" -or
        $planAButtons -notcontains "打开移动热点") {
        throw "Plan A help view did not expose its expected settings actions."
    }
    Add-Report "plan_a_view=visible"
    Add-Report "plan_a_settings_actions=visible_not_invoked"

    Invoke-ButtonByName -Window $planA -Name "← 上一步"
    [void](Wait-ProcessWindow -ProcessId $process.Id -Description "wizard choice view" -Predicate {
        param($window)
        $window.Current.Name -eq "新手向导"
    })
    Add-Report "wizard_back_navigation=passed"
    Add-Report "result=passed"
}
catch {
    Add-Report "result=failed"
    Add-Report "error=$($_.Exception.Message)"
    throw
}
finally {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        Add-Report "process_cleanup=stopped"
    }
    $report | Set-Content -LiteralPath $ReportPath -Encoding utf8
}
