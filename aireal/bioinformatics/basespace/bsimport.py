#!/usr/bin/env python3

import os
import sys
import argparse
import re
import io
import pdb
from collections import defaultdict

import requests

import boto3
from botocore.exceptions import ClientError


trim_lane_regex = re.compile("_L[0-9]{3}$")



def bs_get(url, token, params={}):
    response = requests.get(url, params=params, headers={"x-access-token": token}, stream=True)
    response.raise_for_status()
    return response



def stream_upload(s3_client, download, bucket, key):
    """
    """
    
    # download is a Response object from the requests package
    chunked_download = download.iter_content(chunk_size=8*1024*1024) # 8MB
    
    response = s3_client.create_multipart_upload(Bucket=bucket, Key=key)
    if response["ResponseMetadata"]["HTTPStatusCode"] != 200:
        raise RuntimeError("")
    
    upload_id = response['UploadId']
    file_obj = io.BytesIO()
    parts = []
    
    try:
        while True:
            file_obj.seek(0)
            file_obj.truncate()
            
            n_bytes = 0
            while n_bytes < 512 * 1024 * 1024: # 0.5GB
                try:
                    n_bytes += file_obj.write(next(chunked_download))
                except StopIteration:
                    break

            if file_obj.tell() == 0:
                break
            content_length = file_obj.tell()
            file_obj.seek(0)
            response = s3_client.upload_part(Body=file_obj,
                                             Bucket=bucket, 
                                             Key=key,
                                             ContentLength=content_length,
                                             PartNumber=len(parts) + 1,
                                             UploadId=upload_id)
            parts.append({"ETag": response["ETag"], "PartNumber": len(parts) + 1})
            
        response = s3_client.complete_multipart_upload(Bucket=bucket,
                                                       Key=key,
                                                       MultipartUpload={'Parts': parts},
                                                       UploadId=upload_id)
    except Exception:
        response = s3_client.abort_multipart_upload(Bucket=bucket,
                                                    Key=key,
                                                    UploadId=upload_id)
        raise



def s3_exists(s3_client, bucket, key, size=None):
    try:
        response = s3_client.head_object(Bucket=bucket, Key=key)
        if size is None or response["ContentLength"] == size:
            return True
    except ClientError:
        pass
    return False



def file_exists(path, size=None):
    return os.path.exists(path) and (size is None or os.path.getsize(path) == size)



def post(url, data={}):
    print(data, file=sys.stderr)
    requests.post(url, data=data)



def dont_post(url, data={}):
    print(data, file=sys.stderr)



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("samplenames", nargs="+")
    parser.add_argument("-s", "--server", help="URL of BaseSpace authentication server.", required=True)
    parser.add_argument("-t", "--token", help="BaseSpace authentication token.", required=True)
    parser.add_argument("-a", "--appsession-bsid", help="BaseSpace id of the appsessionn responsible for creating the fastqs to be imported.", required=True)
    parser.add_argument("-o", "--output-dir", help="Path to write imported fastqs to <output-dir>/<experimentname>/<appsession-datecompleted>/<samplename>/<file.fastq>.", required=True)
    parser.add_argument("-c", "--callback", help="URL of the callback to be made to report progress.", default=None, required=False)
    args = parser.parse_args()
    
    callback = post if args.callback else dont_post
    
    S3_OUTPUT = args.output_dir[:5].lower() == "s3://"
    if S3_OUTPUT:
        s3_bucket, s3_prefix = args.output_dir[5:].split("/", maxsplit=1)
        s3_client = boto3.client("s3")
    elif not os.path.isdir(args.output_dir):
        sys.exit(f"output directory {args.output_dir} does not exist")
    
    appsession = bs_get(f"{args.server}/v2/appsessions/{args.appsession_bsid}", args.token).json()
    
    appsession_datecompleted = appsession["DateCompleted"] # ISO8601 with no precision beyond the second eg '2021-08-05T03:41:16.0000000Z'
    appsession_datecompleted = appsession_datecompleted.split(".")[0] # Split off meaningless trailing ".0000000Z"
    
    experimentname = "<EXPERIMENTNAME>"
    datasets = []
    for prop in appsession["Properties"]["Items"]:
        
        if prop["Name"] == "Input.Runs":
            experimentname = prop["RunItems"][0]["ExperimentName"]
        
        elif prop["Name"] == "Output.Datasets":
            if prop["ItemsDisplayedCount"] == prop["ItemsTotalCount"]:
                datasets = prop["DatasetItems"]
            else:
                # Does not specify sort direction in Output.Datasets therefore search from beginning again to be safe.
                total = prop["ItemsTotalCount"]
                url = f"{args.server}/v2/appsessions/{args.appsession_bsid}/properties/Output.Datasets/items"
                while len(datasets) < total:
                    response = bs_get(url, args.token, params={"offset": len(datasets), "SortBy": "DateCreated", "SortDir": "Desc"}).json()
                    for item in response["Items"]:
                        datasets.append(item["Dataset"])
    
    samples = defaultdict(list)
    for dataset in datasets:
        name = dataset["Name"]
        if trim_lane_regex.search(name):
            # If name doe not have a lane suffix then assume it is a composite dataset containing the combined datasets
            # for each of the individual dataset from each lane. WARNING - This assumption may not be future proof but
            # I can see no other way of doing it other than for checking for unique names or etags within the files
            # and this would significantly increase the number of api calls and complexity.
            samples[name[:-5]].append(dataset)
    
    for samplename, datasets in samples.items():
        if samplename in args.samplenames:
            destinations = []
            
            for dataset in datasets:
                try:
                    remaining = 1
                    offset = 0
                    while remaining:
                        response = bs_get(dataset["HrefFiles"], args.token, params={"offset": offset, "SortBy": "DateCreated", "SortDir": "Desc"}).json()
                        paging = response["Paging"]
                        offset = paging["Offset"]
                        remaining = paging["TotalCount"] - offset - paging["DisplayedCount"]
                        for item in response["Items"]:
                            filename = item["Name"]
                            callback(args.callback, data={"name": samplename, "status": "in-progress", "details": filename})
                            identifier = [experimentname, appsession_datecompleted, samplename, filename]
                            
                            download = bs_get(item["HrefContent"], args.token)
                            if S3_OUTPUT:
                                s3_key = "/".join([s3_prefix] + identifier)
                                if not s3_exists(s3_client, s3_bucket, s3_key, size=item["Size"]):
                                    print(f"Copying {filename}", file=sys.stderr)
                                    stream_upload(s3_client, download, s3_bucket, s3_key)
                                else:
                                    print(f"Skipping {filename}", file=sys.stderr)
                                destinations.append(f"s3://{s3_bucket}/{s3_key}")

                            else:
                                path = os.path.join(args.output_dir, *identifier)
                                if not file_exists(path, size=item["Size"]):
                                    print(f"Copying {filename}", file=sys.stderr)
                                    os.makedirs(os.path.dirname(path), exist_ok=True)
                                    with open(path, "wb") as f_out:
                                        for chunk in download.iter_content(chunk_size=8*1024*1024): # 8MB
                                            f_out.write(chunk)
                                else:
                                    print(f"Skipping {filename}", file=sys.stderr)
                                destinations.append(path)
                
                except requests.exceptions.HTTPError as e:
                    callback(args.callback, data={"name": samplename, "status": "failed", "details": e.response.reason})
                    # Crazy but true. BaseSpace will allow access to some objects (files in this case) in a collection but not when accessed directly.
                    # We do not really have access to these and they never should have been included in the collection in the first place. Therefore
                    # ingore and move on to the next sample.
                    if e.response.status_code == 403:
                        print(f"Forbidden {samplename}", file=sys.stderr)
                    else:
                        raise

                except ClientError as e:
                    callback(args.callback, data={"name": samplename, "status": "failed", "details": e.response["Error"]["Code"]})
                    raise

                except Exception as e:
                    callback(args.callback, data={"name": samplename, "status": "failed", "details": str(e)})
                    raise
                
                else:
                    callback(args.callback, data={"name": samplename, "status": "complete", "destinations": destinations})



if __name__ == "__main__":
    main()
