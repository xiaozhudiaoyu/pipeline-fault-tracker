param([string]$jdk, [string]$dir)
$ErrorActionPreference = 'Continue'
$javac = Join-Path $jdk 'bin\javac.exe'
$java  = Join-Path $jdk 'bin\java.exe'
$out   = Join-Path $dir '_out_blindspot'
New-Item -ItemType Directory -Force -Path $out | Out-Null

Write-Output '== 1. compile positive snippets =='
& $javac -encoding UTF-8 -d $out (Join-Path $dir 'GuideBlindSpotSnippets.java')
Write-Output ('javac exit: ' + $LASTEXITCODE)
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Output '== 2. run with -ea =='
& $java -ea -cp $out GuideBlindSpotSnippets
Write-Output ('java exit: ' + $LASTEXITCODE)
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Output '== 3. negative: final reassignment MUST fail compile =='
& $javac -encoding UTF-8 -d $out (Join-Path $dir 'GuideFinalNegative.java') 2>&1 | Out-String | Write-Output
Write-Output ('javac exit (expect nonzero): ' + $LASTEXITCODE)
if ($LASTEXITCODE -eq 0) { Write-Output 'NEGATIVE TEST FAILED: doc claim falsified'; exit 1 }

Write-Output '== 4. assert default-off =='
& $javac -encoding UTF-8 -d $out (Join-Path $dir 'GuideAssertOff.java')
& $java -cp $out GuideAssertOff
Write-Output ('java no-ea exit (expect 0): ' + $LASTEXITCODE)
if ($LASTEXITCODE -ne 0) { exit 1 }
& $java -ea -cp $out GuideAssertOff 2>&1 | Out-String | Write-Output
Write-Output ('java -ea exit (expect nonzero): ' + $LASTEXITCODE)
if ($LASTEXITCODE -eq 0) { Write-Output 'ASSERT TEST FAILED'; exit 1 }

Write-Output 'ALL VERIFICATIONS PASSED'