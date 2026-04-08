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
