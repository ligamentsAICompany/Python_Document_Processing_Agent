# Install PageIndex dependencies into the active environment (e.g. conda myenv).
# Fixes: PageIndex/requirements.txt vs litellm python-dotenv conflict.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Installing PageIndex deps from requirements-pageindex.txt ..."
pip install -r requirements-pageindex.txt

Write-Host "Done. Verify: python -c `"import litellm; import fitz; print('PageIndex deps OK')`""
