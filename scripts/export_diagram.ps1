param([string]$Npx = "npx")

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    & $Npx --yes --package "@mermaid-js/mermaid-cli" mmdc -p (Join-Path $repoRoot ".github\puppeteer-config.json") -i docs\diagrams\value_chain.mmd -o docs\diagrams\value_chain.svg -b white
    if ($LASTEXITCODE -ne 0) {
        throw "Mermaid export failed (exit code $LASTEXITCODE)"
    }
}
finally {
    Pop-Location
}
