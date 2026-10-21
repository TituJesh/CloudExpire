
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PackagePath = Join-Path $ProjectRoot "lambda\package"
$AppPath = Join-Path $ProjectRoot "app"
$HandlerPath = Join-Path $ProjectRoot "lambda\src\cleanup_handler.py"

if (Test-Path $PackagePath) {
    Remove-Item $PackagePath -Recurse -Force
}

New-Item -ItemType Directory -Force $PackagePath | Out-Null

Copy-Item $HandlerPath (Join-Path $PackagePath "cleanup_handler.py")
Copy-Item $AppPath (Join-Path $PackagePath "app") -Recurse

Get-ChildItem (Join-Path $PackagePath "app") -Directory -Filter "__pycache__" -Recurse |
    Remove-Item -Recurse -Force

docker run --rm --entrypoint /bin/sh `
    -v "${PackagePath}:/var/task" `
    -w /var/task `
    public.ecr.aws/lambda/python:3.12 `
    -c "pip install --retries 10 --timeout 120 --target . pydantic boto3"

if ($LASTEXITCODE -ne 0) {
    throw "Lambda dependency installation failed."
}

Write-Host "Lambda deployment package built successfully."
