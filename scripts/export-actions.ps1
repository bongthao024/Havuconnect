param([Parameter(Mandatory=$true)][string]$PublicUrl)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force .local | Out-Null
& .\.venv\Scripts\python.exe -m gpt_pc_control.actions --public-url $PublicUrl --output .local\actions-openapi.json
if ($LASTEXITCODE -ne 0) { throw 'Không xuất được schema' }
Write-Host 'Nhập nội dung .local\actions-openapi.json vào GPT Builder > Actions.'
