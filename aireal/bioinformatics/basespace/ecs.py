import pdb

import boto3


task_definitions = {}
preferred_subnet = ""


def run_task(task, command, availability_zone=""):
    """ 
    """
    global preferred_subnet
    ecs = boto3.client("ecs")
    #subnet = current_app.config["AWS_SUBNET"]

    for tries in (0, 1):
        if task in task_definitions and preferred_subnet:
            response = ecs.run_task(
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
            print(response)
        
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



if __name__ == "__main__":
    args = ["HL040821-21IDT023-c-0-1B",
            "--server", "https://api.basespace.illumina.com",
            "--token", "c0f7043e49de4dd1a67735140e89d97a",
            "--appsession-bsid", "496196702",
            "--output-dir", "s3://omdc-data/projects/zzzz/samples"]
    
    run_task("BSImport", args, availability_zone="eu-west-2b")
