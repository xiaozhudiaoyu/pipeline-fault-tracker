param([string]$path)
Select-String -Path $path -Pattern '^### ' | ForEach-Object { '{0}: {1}' -f $_.LineNumber, $_.Line }