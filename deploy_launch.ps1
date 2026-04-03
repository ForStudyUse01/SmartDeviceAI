$ErrorActionPreference = "Continue"
$env:PATH += ";C:\Program Files\Amazon\AWSCLIV2"

Remove-Item -Path ".\backend\.venv" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path ".\backend\__pycache__" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Compressing backend..."
Compress-Archive -Path ".\backend\*" -DestinationPath "backend.zip" -Force

Write-Host "Uploading backend.zip to S3..."
aws s3 cp backend.zip s3://sb-project-frontend-639106563101697350/backend.zip

$userData = @"
#!/bin/bash
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1
yum update -y
yum install -y python3 python3-pip unzip wget
aws s3 cp s3://sb-project-frontend-639106563101697350/backend.zip /home/ec2-user/backend.zip
cd /home/ec2-user
unzip backend.zip -d backend
cd backend
pip3 install -r requirements.txt
nohup python3 app.py > server.log 2>&1 &
"@
Set-Content "userdata.sh" -Value $userData -Encoding Ascii

Write-Host "Discovering SG and AMI..."
$sgId = (aws ec2 describe-security-groups --group-names sb-project-sg --query 'SecurityGroups[0].GroupId' --output text)
$amiId = (aws ec2 describe-images --owners amazon --filters "Name=name,Values=al2023-ami-2023.*-x86_64" "Name=state,Values=available" --query "sort_by(Images, &CreationDate)[-1].ImageId" --output text)

Write-Host "Launching EC2 using t3.micro..."
$instanceId = (aws ec2 run-instances --image-id $amiId --count 1 --instance-type t3.micro --key-name sb-project-key --security-group-ids $sgId --iam-instance-profile Name=sb-project-ec2-profile --user-data "file://userdata.sh" --query 'Instances[0].InstanceId' --output text)

Write-Host "Waiting for instance to be running..."
aws ec2 wait instance-running --instance-ids $instanceId
$publicIp = (aws ec2 describe-instances --instance-ids $instanceId --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

Write-Host "EC2_PUBLIC_IP: $publicIp"
$output = "FINAL_CF_DOMAIN: d1lm13ui785dx0.cloudfront.net`nFINAL_EC2_IP: $publicIp"
Set-Content -Path results.txt -Value $output -Encoding Ascii
Write-Host "Done!"
