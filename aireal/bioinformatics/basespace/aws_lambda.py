import json
import requests
import tempfile
import boto3
import pdb



def invoke(name, **payload):
    client = boto3.client("lambda")
    
    response = client.invoke(FunctionName=name,
                             InvocationType="Event",
                             LogType="None",
                             ClientContext="",
                             Payload=json.dumps(payload))
    pdb.set_trace()


def multipart_upload(event, context):
    key = event["key"]
    bucket = event["bucket"]
    url = event["url"]
    
    response = requests.get(url, stream=True)
    response.raise_for_status()
    iter_content = response.iter_content(chunk_size=8 * 1024)
    
    client = boto3.client("s3")
    response = client.create_multipart_upload(Bucket=bucket, 
                                              Key=key)
    if response["ResponseMetadata"]["HTTPStatusCode"] != 200:
        raise
    try:
        upload_id = response['UploadId']
        
        part_number = 0
        parts = []
        while True:
            with tempfile.TemporaryFile() as f_obj:
                n_bytes = 0
                while n_bytes < 50 * 1024 * 1024:
                    try:
                        n_bytes += f_obj.write(next(iter_content))
                    except StopIteration:
                        break

                if f_obj.tell() == 0:
                    break
                content_length = f_obj.tell()
                f_obj.seek(0)
                part_number += 1
                response = client. \
                            upload_part(Body=f_obj,
                                        Bucket=bucket, 
                                        Key=key,
                                        ContentLength=content_length,
                                        PartNumber=part_number,
                                        UploadId=upload_id)
                parts += [{"ETag": response["ETag"],
                           "PartNumber": part_number}]

        response = client. \
                    complete_multipart_upload(Bucket=bucket,
                                              Key=key,
                                              MultipartUpload={'Parts': parts},
                                              UploadId=upload_id)
    except Exception:
        response = client. \
                    abort_multipart_upload(Bucket=bucket,
                                           Key=key,
                                           UploadId=upload_id)
        raise

    return {"statusCode": 200,
            "body": json.dumps(f"{key} uploaded to {bucket}")}


