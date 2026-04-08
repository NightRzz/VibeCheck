param(
    [int]$Count = 12,
    [int]$DelayMs = 750,
    [string]$Uri = "http://localhost:8001/ingest"
)

$ErrorActionPreference = "Stop"

$sampleTexts = @(
    "This launch feels smooth and reliable.",
    "I love how responsive this pipeline is.",
    "This is terrible and constantly broken.",
    "The dashboard is useful but still a bit rough.",
    "Absolutely fantastic experience so far.",
    "I am frustrated by the delays today.",
    "This feels stable, fast, and clean.",
    "The service is failing and I do not trust it.",
    "Pretty neutral update, nothing major changed.",
    "This is the best result we have seen all week."
)

for ($index = 0; $index -lt $Count; $index++) {
    $text = Get-Random -InputObject $sampleTexts
    $body = @{
        source_id = "test_user_$($index + 1)"
        text = $text
    } | ConvertTo-Json -Compress

    $response = Invoke-RestMethod `
        -Uri $Uri `
        -Method Post `
        -Headers @{ "Content-Type" = "application/json" } `
        -Body $body

    Write-Host "[$($index + 1)/$Count] offset=$($response.offset) text=$text"

    if ($index -lt ($Count - 1)) {
        Start-Sleep -Milliseconds $DelayMs
    }
}
