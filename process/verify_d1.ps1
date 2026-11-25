# D1 验证脚本：逐条校验「正常 + 异常」请求，输出状态码与 422 details。
# 仅新增测试数据（POST/PATCH），不删改既有记录；用完可按输出中的 id 人工清理。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$base = 'http://127.0.0.1:8000/api'
$now = Get-Date

function Show-Result([string]$name, [scriptblock]$action) {
    try {
        $resp = & $action
        Write-Host "== $name => OK" -ForegroundColor Green
        if ($resp -is [string]) { Write-Host $resp }
    } catch {
        $r = $_.Exception.Response
        if ($r) {
            $code = [int]$r.StatusCode
            # PS5.1 下 Invoke-RestMethod 的错误体优先从 ErrorDetails 取，流读取仅作兜底
            $body = $_.ErrorDetails.Message
            if (-not $body) {
                try { $body = (New-Object System.IO.StreamReader($r.GetResponseStream())).ReadToEnd() } catch { $body = '(无法读取响应体)' }
            }
            Write-Host "== $name => HTTP $code" -ForegroundColor Yellow
            Write-Host $body
        } else {
            Write-Host "== $name => 请求失败: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}

function Post-Fault($bodyObj) {
    Invoke-RestMethod -Uri "$base/faults" -Method Post -ContentType 'application/json; charset=utf-8' `
        -Body ([System.Text.Encoding]::UTF8.GetBytes(($bodyObj | ConvertTo-Json -Depth 5)))
}
function Patch-Fault($id, $bodyObj) {
    Invoke-RestMethod -Uri "$base/faults/$id" -Method Patch -ContentType 'application/json; charset=utf-8' `
        -Body ([System.Text.Encoding]::UTF8.GetBytes(($bodyObj | ConvertTo-Json -Depth 5)))
}
function Patch-Transition($id, $bodyObj) {
    Invoke-RestMethod -Uri "$base/faults/$id/transition" -Method Patch -ContentType 'application/json; charset=utf-8' `
        -Body ([System.Text.Encoding]::UTF8.GetBytes(($bodyObj | ConvertTo-Json -Depth 5)))
}

$validBody = @{
    pipeline_id = 1
    location    = '3号工位传送带'
    occurred_at = $now.AddHours(-1).ToString('yyyy-MM-ddTHH:mm:ss')
    symptom     = '传送带运行时有异响并偶发卡顿'
}

function New-Body([hashtable]$overrides) {
    # PS5.1 不支持 hashtable 相加合并，用克隆+覆盖构造变体请求体
    $b = $validBody.Clone()
    foreach ($k in $overrides.Keys) { $b[$k] = $overrides[$k] }
    return $b
}

Write-Host "`n---- 1. FaultCreate 边界校验 ----"
Show-Result '1.1 正常登记（期望 201）' { Post-Fault $validBody | ConvertTo-Json -Depth 3 -Compress }
Show-Result '1.2 occurred_at 未来时间（期望 422）' {
    Post-Fault (New-Body @{ occurred_at = $now.AddDays(1).ToString('yyyy-MM-ddTHH:mm:ss') })
}
Show-Result '1.3 symptom 超 1000 字（期望 422）' {
    Post-Fault (New-Body @{ symptom = ('故' * 1001) })
}
Show-Result '1.4 location 首字符空白（期望 422）' {
    Post-Fault (New-Body @{ location = ' 3号工位传送带' })
}
Show-Result '1.5 symptom 仅 4 字（既有规则回归，期望 422）' {
    Post-Fault (New-Body @{ symptom = '异响卡顿' })
}
Show-Result '1.6 多传未知字段（既有 extra=forbid 回归，期望 422）' {
    Post-Fault (New-Body @{ status = 'done' })
}

Write-Host "`n---- 2. FaultTransition：说明一旦提供 ≥5 字 ----"
# 新建一条 pending 供流转测试
$f = Post-Fault $validBody
Write-Host "测试用故障 id=$($f.id)（pending）"
Show-Result '2.1 note="ok" 推进 processing（期望 422）' {
    Patch-Transition $f.id @{ target_status = 'processing'; handling_note = 'ok' }
}
Show-Result '2.2 note="     x"（5空格+1字，期望 422）' {
    Patch-Transition $f.id @{ target_status = 'processing'; handling_note = '     x' }
}
Show-Result '2.3 note=null 推进 processing（期望 200，本次不改说明）' {
    Patch-Transition $f.id @{ target_status = 'processing'; handling_note = $null } | ConvertTo-Json -Depth 3 -Compress
}
Show-Result '2.4 note="已紧固螺栓并空载试运行验证" 推进 done（期望 200）' {
    Patch-Transition $f.id @{ target_status = 'done'; handling_note = '已紧固螺栓并空载试运行验证' } | ConvertTo-Json -Depth 3 -Compress
}

Write-Host "`n---- 3. PATCH /{id}：done 后 handling_note 锁定 ----"
Show-Result '3.1 done 后改 handling_note（期望 409 handling_note_locked）' {
    Patch-Fault $f.id @{ handling_note = '试图事后篡改结案说明内容' }
}
Show-Result '3.2 done 后改 symptom（期望 200，基础信息可维护）' {
    Patch-Fault $f.id @{ symptom = '传送带异响与卡顿（补充：紧固后复测正常）' } | ConvertTo-Json -Depth 3 -Compress
}
Show-Result '3.3 symptom 超短（期望 422）' {
    Patch-Fault $f.id @{ symptom = '异响' }
}
Show-Result '3.4 handling_note 显式 null（期望 422，不支持清空）' {
    Patch-Fault $f.id @{ handling_note = $null }
}
Show-Result '3.5 不存在的 id（期望 404 fault_not_found）' {
    Patch-Fault 999999 @{ symptom = '任意内容五条字数以上' }
}
# 非 done 记录改说明（回归：pending/processing 应放行）
$f2 = Post-Fault $validBody
Show-Result "3.6 pending 记录(id=$($f2.id))改 handling_note（期望 200）" {
    Patch-Fault $f2.id @{ handling_note = '已安排维修工跟进排查' } | ConvertTo-Json -Depth 3 -Compress
}

Write-Host "`n---- 4. 既有接口回归 ----"
Show-Result '4.1 GET /faults（期望 200）' {
    (Invoke-RestMethod -Uri "$base/faults?page=1&size=5") | ForEach-Object { "total=$($_.total) items=$($_.items.Count)" }
}
Show-Result '4.2 GET /faults?status=done（期望 200）' {
    (Invoke-RestMethod -Uri "$base/faults?status=done") | ForEach-Object { "total=$($_.total)" }
}
Show-Result '4.3 GET /faults/1（期望 200）' {
    (Invoke-RestMethod -Uri "$base/faults/1") | ForEach-Object { "id=$($_.id) status=$($_.status)" }
}
Show-Result '4.4 GET /pipelines（期望 200）' {
    (Invoke-RestMethod -Uri "$base/pipelines") | ForEach-Object { $_.code } 
}
Write-Host "`n验证脚本执行完毕。"
