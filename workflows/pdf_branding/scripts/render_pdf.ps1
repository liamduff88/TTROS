param(
  [Parameter(Mandatory = $true)]
  [string]$InputPath,

  [Parameter(Mandatory = $true)]
  [string]$OutputPath
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Renderer = Join-Path $ScriptDir "render_pdf.py"
$WorkflowRoot = Split-Path -Parent $ScriptDir
$WorkspaceRoot = Split-Path -Parent (Split-Path -Parent $WorkflowRoot)
$VenvPython = Join-Path $WorkspaceRoot ".venv-pdf/bin/python"

if (Test-Path $VenvPython) {
  & $VenvPython $Renderer --input $InputPath --output $OutputPath
} else {
  python3 $Renderer --input $InputPath --output $OutputPath
}
