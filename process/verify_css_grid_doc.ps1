# Verify TOC anchors vs headings in CSS_GRID.md (ASCII-only script body)
$path = Join-Path $PSScriptRoot '..\guide_file\CSS_GRID.md'
$lines = Get-Content -Path $path -Encoding UTF8

function Get-anchor([string]$heading) {
    # strip leading #'s, lowercase, remove punctuation kept from CJK/alnum, spaces->hyphen
    $t = ($heading -replace '^#+\s*', '')
    $t = $t.ToLower()
    $t = $t -replace '[^\p{L}\p{N}\s\-`]', ''
    $t = $t -replace '`', ''
    $t = $t -replace '\s', '-'
    return $t
}

$headings = @{}
foreach ($l in $lines) {
    if ($l -match '^#{2,3}\s') { $headings[(Get-anchor $l)] = $true }
}

$tocLinks = @()
foreach ($l in $lines) {
    if ($l -match '^\d+\.\s+\[.*\]\(#([^)]+)\)') { $tocLinks += $Matches[1] }
}
$fail = 0
function Dump-codepoints([string]$s) {
    ($s.ToCharArray() | ForEach-Object { '{0:X4}' -f [int]$_ }) -join ' '
}
foreach ($a in $tocLinks) {
    if (-not $headings.ContainsKey($a)) {
        Write-Output ("MISSING-HEADING: " + $a)
        Write-Output ("  toc-anchor codepoints: " + (Dump-codepoints $a))
        # find closest heading by prefix to dump for comparison
        $prefix = $a.Substring(0, [Math]::Min(4, $a.Length))
        foreach ($k in $headings.Keys) {
            if ($k.StartsWith($prefix)) {
                Write-Output ("  closest heading    : " + $k)
                Write-Output ("  heading codepoints : " + (Dump-codepoints $k))
            }
        }
        $fail++
    }
}
Write-Output ("TOC entries checked: " + $tocLinks.Count)

# verify cross references like (see pit 12.x / [12.1](#...)) targets exist
$refs = @()
foreach ($l in $lines) {
    $ms = [regex]::Matches($l, '\(#(12\d-[a-z0-9\-%\u4e00-\u9fff]+)\)')
    foreach ($m in $ms) { $refs += $m.Groups[1].Value }
}
foreach ($a in ($refs | Select-Object -Unique)) {
    if (-not $headings.ContainsKey($a)) { Write-Output ("DEAD-REF: " + $a); $fail++ }
}
Write-Output ("Inline pit refs checked: " + ($refs | Select-Object -Unique).Count)

# verify continuity of ### x.y numbering WITHIN each chapter (chapters may have no subsections)
$nums = @()
foreach ($l in $lines) {
    if ($l -match '^### (\d+)\.(\d+)\s') { $nums += ,@([int]$Matches[1], [int]$Matches[2]) }
}
$byChapter = $nums | Group-Object { $_[0] }
foreach ($g in $byChapter) {
    $seq = $g.Group | ForEach-Object { $_[1] }
    $expected = 1
    foreach ($v in $seq) {
        if ($v -ne $expected) { Write-Output ("SUBSEQ-GAP in chapter " + $g.Name + ": got " + $v + " expected " + $expected); $fail++ }
        $expected = $v + 1
    }
}
Write-Output ("Sub-headings checked: " + $nums.Count)
if ($fail -eq 0) { Write-Output "ALL CHECKS PASSED" } else { Write-Output ("FAILURES: " + $fail) }
exit $fail
