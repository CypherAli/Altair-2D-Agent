$desk = [Environment]::GetFolderPath('Desktop')
$src = 'C:\Users\trinh\Downloads\AI_AGENT'
$lnk = Join-Path $desk 'Ali Studio.lnk'
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = Join-Path $src 'AliStudio.bat'
$s.WorkingDirectory = $src
$s.IconLocation = (Join-Path $src 'AliStudio.ico')
$s.Description = 'Ali Studio - Local Workspace'
$s.Save()
Write-Host "LNK_OK $lnk"
