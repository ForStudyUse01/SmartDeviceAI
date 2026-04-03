$ErrorActionPreference = "Continue"
$env:PATH += ";C:\Program Files\Amazon\AWSCLIV2"

Write-Host "Creating IAM Role..."
$trustPolicy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ec2.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
"@
Set-Content -Path trust-policy.json -Value $trustPolicy -Encoding Ascii
aws iam create-role --role-name sb-project-ec2-role --assume-role-policy-document file://trust-policy.json | Out-Null
aws iam attach-role-policy --role-name sb-project-ec2-role --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess | Out-Null
aws iam create-instance-profile --instance-profile-name sb-project-ec2-profile | Out-Null
aws iam add-role-to-instance-profile --instance-profile-name sb-project-ec2-profile --role-name sb-project-ec2-role | Out-Null

Start-Sleep -Seconds 10

Write-Host "Creating Key Pair..."
aws ec2 create-key-pair --key-name sb-project-key --query 'KeyMaterial' --output text | Out-File -FilePath sb-project-key.pem -Encoding Ascii

Write-Host "Creating Security Group..."
$vpcId = (aws ec2 describe-vpcs --query 'Vpcs[0].VpcId' --output text)
$sgId = (aws ec2 create-security-group --group-name sb-project-sg --description "SG for SB project" --vpc-id $vpcId --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id $sgId --protocol tcp --port 22 --cidr 0.0.0.0/0 | Out-Null
aws ec2 authorize-security-group-ingress --group-id $sgId --protocol tcp --port 8000 --cidr 0.0.0.0/0 | Out-Null
aws ec2 authorize-security-group-ingress --group-id $sgId --protocol tcp --port 80 --cidr 0.0.0.0/0 | Out-Null

Write-Host "Launching EC2 instance..."
$amiId = (aws ec2 describe-images --owners amazon --filters "Name=name,Values=al2023-ami-2023.*-x86_64" "Name=state,Values=available" --query "sort_by(Images, &CreationDate)[-1].ImageId" --output text)

$instanceId = (aws ec2 run-instances --image-id $amiId --count 1 --instance-type t2.micro --key-name sb-project-key --security-group-ids $sgId --iam-instance-profile Name=sb-project-ec2-profile --query 'Instances[0].InstanceId' --output text)

Write-Host "Waiting for EC2 to run..."
aws ec2 wait instance-running --instance-ids $instanceId
$publicIp = (aws ec2 describe-instances --instance-ids $instanceId --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
Write-Host "EC2 is running! InstanceId: $instanceId"
Write-Host "FINAL_EC2_IP: $publicIp"

$output = "FINAL_CF_DOMAIN: d1lm13ui785dx0.cloudfront.net`nFINAL_EC2_IP: $publicIp"
Set-Content -Path results.txt -Value $output -Encoding Ascii
