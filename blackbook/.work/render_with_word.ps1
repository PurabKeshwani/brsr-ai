param(
  [Parameter(Mandatory=$true)][string]$InputDocx,
  [Parameter(Mandatory=$true)][string]$OutputPdf,
  [string]$LayoutJson,
  [switch]$SaveUpdatedDocument
)
$ErrorActionPreference = 'Stop'
$docPath = (Resolve-Path -LiteralPath $InputDocx).Path
$pdfPath = [IO.Path]::GetFullPath($OutputPdf)
$outParent = [IO.Path]::GetDirectoryName($pdfPath)
[IO.Directory]::CreateDirectory($outParent) | Out-Null
$wordApp = $null
$wordDoc = $null
try {
  $wordApp = New-Object -ComObject Word.Application
  $wordApp.Visible = $false
  $wordApp.DisplayAlerts = 0
  $wordApp.AutomationSecurity = 3
  $wordApp.Options.SaveNormalPrompt = $false
  $wordDoc = $wordApp.Documents.Open($docPath, $false, $false, $false)
  $wordDoc.Fields.Update() | Out-Null
  foreach ($tocItem in $wordDoc.TablesOfContents) { $tocItem.Update() }
  foreach ($tofItem in $wordDoc.TablesOfFigures) { $tofItem.Update() }
  $wordDoc.Repaginate()
  $wordDoc.Fields.Update() | Out-Null
  foreach ($tocItem in $wordDoc.TablesOfContents) { $tocItem.UpdatePageNumbers() }
  foreach ($tofItem in $wordDoc.TablesOfFigures) { $tofItem.UpdatePageNumbers() }
  $wordDoc.Repaginate()
  $pageCount = $wordDoc.ComputeStatistics(2)
  if ($SaveUpdatedDocument) { $wordDoc.Save() }
  $wordDoc.ExportAsFixedFormat($pdfPath, 17, $false, 0, 0, 1, 1, 0, $true, $true, 1, $true, $true, $false)
  $layout = [ordered]@{ source=$docPath; pdf=$pdfPath; pages=$pageCount; engine='Microsoft Word COM, invisible instance'; fields_updated=$true; saved_updated_docx=[bool]$SaveUpdatedDocument; exported_at_utc=[DateTime]::UtcNow.ToString('o') }
  if ($LayoutJson) { $layout | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $LayoutJson -Encoding UTF8 }
  $layout | ConvertTo-Json -Compress
} finally {
  if ($null -ne $wordDoc) { $wordDoc.Close(0); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordDoc) }
  if ($null -ne $wordApp) { $wordApp.Quit(0); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordApp) }
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}
