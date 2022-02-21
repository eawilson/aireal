from datetime import datetime, timedelta
import requests
import pdb
import json

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from botocore.signers import CloudFrontSigner

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config

from flask import current_app
from werkzeug import exceptions

from .i18n import _

__all__ = [
    "ec2_metadata",
    "s3_sign_url",
    "cloudfront_sign_url",
    "cloudfront_sign_cookies",
    "sendmail",
    "list_objects",
    "object_exists",
    "run_task"]


# Caching to reduce need for repeated api calls. They
task_definitions = {}
preferred_subnet = ""


def ec2_metadata():
    """ Get metadata about current running instance.
    """
    BASE_URL = "http://169.254.169.254/latest"
    metadata = {}
    session = requests.Session()
    try:
        response = session.put(f"{BASE_URL}/api/token",
                            headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
                            timeout=3.0)
    except requests.exceptions.ConnectionError:
        return metadata
    if response.status_code != 200:
        return metadata
    session.headers.update({"X-aws-ec2-metadata-token": response.text})
    
    
    response = session.get(f"{BASE_URL}/meta-data/placement/availability-zone",
                           timeout=2.0)
    if response.status_code == 200:
        metadata["AWS_AVAILABILITY_ZONE"] = response.text
        metadata["AWS_REGION"] = response.text[:-1]
        
    return metadata
    #response = session.get(f"{BASE_URL}/meta-data/placement/region",
                           #timeout=2.0)
    #if response.status_code == 200:
        #metadata["AWS_REGION"] = response.text
    
    #response = session.get(f"{BASE_URL}/meta-data/mac",
                           #timeout=2.0)
    #if response.status_code == 200:
        #mac = response.text
        #response = session.get(f"{BASE_URL}/meta-data/network/interfaces/macs/{mac}/subnet-id",
                           #timeout=2.0)
        #if response.status_code == 200:
            #metadata["AWS_SUBNET"] = response.text

        #response = session.get(f"{BASE_URL}/meta-data/network/interfaces/macs/{mac}/subnet-ipv4-cidr-block",
                           #timeout=2.0)
        #if response.status_code == 200:
            #metadata["LOCAL_SUBNET"] = response.text



def rsa_signer(key_id):
    def rsa_signer(message):
        with open(f"{key_id}_private_key.pem", "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None,
                backend=default_backend()
                )
        return private_key.sign(message, padding.PKCS1v15(), hashes.SHA1())
    return rsa_signer



def cloudfront_sign_url(url, key_id, **offset):
    expires_datetime = datetime.now() + timedelta(**(offset or {"days": 1}))
    cloudfront_signer = CloudFrontSigner(key_id, rsa_signer(key_id))
    return cloudfront_signer.generate_presigned_url(url, date_less_than=expires_datetime)



def cloudfront_sign_cookies(url, key_id, **offset):
    expires_datetime = datetime.now() + timedelta(**(offset or {"days": 1}))
    rsa_sign = rsa_signer(key_id)
    cloudfront_signer = CloudFrontSigner(key_id, rsa_sign)
    
    policy = cloudfront_signer.build_policy(url, expires_datetime).encode("utf8")
    policy_64 = cloudfront_signer._url_b64encode(policy).decode("utf8")
    signature = rsa_sign(policy)
    signature_64 = cloudfront_signer._url_b64encode(signature).decode('utf8')
    cookies =  {"CloudFront-Policy": policy_64,
                "CloudFront-Signature": signature_64,
                "CloudFront-Key-Pair-Id": key_id}
    return json.dumps(cookies)



def s3_sign_url(bucket, key, **offset):
    expires = int(timedelta(**(offset or {"days": 1})).total_seconds())
    print(expires)
    client = boto3.client("s3", config=Config(s3={"use_accelerate_endpoint": True}))
    return client.generate_presigned_url(ClientMethod="put_object",
                                         ExpiresIn=expires,
                                         Params={"Bucket": bucket, "Key": key})
                                                 #"ContentType": "binary/octet-stream"})
                                         



def sendmail(recipients, subject, body):
    config = current_app.config
    
    sender = config.get("MAIL_SENDER")
    region = config.get("MAIL_REGION")
    if not (sender or region):
        raise exceptions.NotImplemented(_("Not configured to send email. Please contact an administrator."))
    
    if isinstance(recipients, str):
        recipients = recipients.split(",")
    
    client = boto3.client('ses', region_name=region)

    try:
        response = client.send_email(
            Destination={'ToAddresses': recipients,
                        },
            Message={'Body': {'Text': {'Charset': "UTF-8",
                                       'Data': body,
                                      },
                             },
                     'Subject': {'Charset': "UTF-8",
                                 'Data': subject,
                                },
                    },
            Source=sender,
            )
    	
    except ClientError as e:
        raise exceptions.InternalServerError(_("Unable to send email at the present time. Please contact an administrator if this problem persists."))



def list_objects(bucket, prefix):
    """ Returns a dict of all objects in bucket that have the specified prefix
    """
    client = boto3.client("s3")
    response = {}
    kwargs = {}
    keys = {}
    while response.get("IsTruncated", True):
        response = client.list_objects_v2(Bucket=bucket, Prefix=prefix, **kwargs)
        for content in response.get("Contents", ()):
            keys[content["Key"]] = content
        kwargs = {"ContinuationToken": response.get("NextContinuationToken", None)}
    return keys



def object_exists(bucket, path):
    """
    """
    client = boto3.client("s3")
    response = {}
    kwargs = {}
    while response.get("IsTruncated", True):
        response = client.list_objects_v2(Bucket=bucket, Prefix=prefix, **kwargs)
        for content in response.get("Contents", ()):
            if content["Key"] == path:
                return True
        kwargs = {"ContinuationToken": response.get("NextContinuationToken", None)}
    return False



def run_task(task, command):
    """ 
    """
    global preferred_subnet
    global task_definitions
    config = current_app.config
    availability_zone = config.get("AWS_AVAILABILITY_ZONE", "") or (config.get("AWS_REGION", "") + "?")
    
    ecs = boto3.client("ecs")
    #subnet = current_app.config["AWS_SUBNET"]
    
    for tries in (0, 1):
        retval = {}
        if task in task_definitions and preferred_subnet:
            try:
                retval = ecs.run_task(
                    taskDefinition = task_definitions[task],
                    launchType = "FARGATE",
                    networkConfiguration = {
                        "awsvpcConfiguration": {
                            "subnets": [preferred_subnet],
                            "assignPublicIp": "ENABLED",
                            }
                        },
                    overrides = {
                        "containerOverrides": [{
                                "name": task,
                                "command": command,
                                }],
                        }
                    )
                if retval["ResponseMetadata"]["HTTPStatusCode"] == 200:
                    break
            except BotoCoreError:
                pass
        
        if tries == 0: 
            response = None
            next_token = {}
            while response is None or "nextToken" in response:
                response = ecs.list_task_definitions(**next_token)
                next_token = {"nextToken": response.get("nextToken", "")}
                if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                    # Sorted asc so latest definition appears last
                    for arn in response["taskDefinitionArns"]:
                        name = arn.split("/")[-1].split(":")[0]
                        task_definitions[name] = arn
            
            if preferred_subnet == "":
                next_best_subnet = any_subnet = ""
                response = None
                next_token = {}
                while response is None or "nextToken" in response:
                    ec2 = boto3.client("ec2")
                    response = ec2.describe_subnets(**next_token)
                    next_token = {"nextToken": response.get("nextToken", "")}
                    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                        # Sorted asc so latest definition appears last
                        for subnet in response["Subnets"]:
                            for tag in subnet.get("Tags", ()):
                                if tag["Key"] == "Name" and tag["Value"].startswith("ECS default "):
                                    if subnet["AvailabilityZone"] == availability_zone:
                                        preferred_subnet = subnet["SubnetId"]
                                    elif subnet["AvailabilityZone"][:-1] == availability_zone[:-1]:
                                        next_best_subnet = subnet["SubnetId"]
                                    else:
                                        any_subnet = subnet["SubnetId"]
                                    break
                preferred_subnet = preferred_subnet or next_best_subnet or any_subnet
    
    return retval
    
    
