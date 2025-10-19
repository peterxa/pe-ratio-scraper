# ================================
# DEPLOY FASTAPI TO AWS LAMBDA (via S3)
# ================================

# Configuración
$bucketName = "myapilambdayfinance"          # Cambia por tu bucket S3
$s3Key = "lambda-deploy.zip"              # Nombre del archivo en S3
$lambdaFunctionName = "fastapi-lambda"
$region = "us-east-2"

# Limpiar contenedores temporales previos
Write-Host "Limpiando contenedores temporales..."
docker rm -f temp-lambda 2>$null

# Limpiar archivos previos
if (Test-Path .\lambda-package) { Remove-Item -Recurse -Force .\lambda-package }
if (Test-Path .\lambda-deploy.zip) { Remove-Item -Force .\lambda-deploy.zip }

# Build de Docker
Write-Host "Building Docker image..."
docker build -t fastapi-lambda .
if ($LASTEXITCODE -ne 0) {
  Write-Error "ERROR: Docker build falló"
  exit
}

# Crear contenedor temporal
Write-Host "Creating container..."
docker create --name temp-lambda fastapi-lambda
if ($LASTEXITCODE -ne 0) {
  Write-Error "ERROR: Docker create falló"
  exit
}

# Copiar archivos al host
Write-Host "Copying build from container..."
docker cp temp-lambda:/var/task ./lambda-package
if ($LASTEXITCODE -ne 0) {
  Write-Error "ERROR: docker cp falló"
  exit
}

# Eliminar contenedor temporal
Write-Host "Cleaning temporary container..."
docker rm temp-lambda 2>$null

# Validar carpeta
if (!(Test-Path .\lambda-package)) {
  Write-Error "ERROR: lambda-package no existe."
  exit
}

# Crear ZIP
Write-Host "Creating ZIP package..."
Compress-Archive -Path .\lambda-package\* -DestinationPath .\lambda-deploy.zip -Force

if (!(Test-Path .\lambda-deploy.zip)) {
  Write-Error "ERROR: No se pudo crear lambda-deploy.zip"
  exit
}

# Subir ZIP a S3
Write-Host "Uploading ZIP to S3..."
aws s3 cp .\lambda-deploy.zip s3://$bucketName/$s3Key --region $region
if ($LASTEXITCODE -ne 0) {
  Write-Error "ERROR: No se pudo subir ZIP a S3"
  exit
}

# Deploy a Lambda desde S3
Write-Host "Deploying to AWS Lambda from S3..."
aws lambda update-function-code `
  --function-name $lambdaFunctionName `
  --s3-bucket $bucketName `
  --s3-key $s3Key `
  --region $region

if ($LASTEXITCODE -ne 0) {
  Write-Error "ERROR: Deployment falló"
  exit
}

Write-Host "Deployment complete!"
