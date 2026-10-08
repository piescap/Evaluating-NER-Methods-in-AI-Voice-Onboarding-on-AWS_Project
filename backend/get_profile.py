import json
import boto3
from botocore.exceptions import ClientError
import traceback

s3 = boto3.client('s3')

# Put the exact name of your S3 bucket here
BUCKET_NAME = "file-output-profilo-onboarding"  # WARNING: remove trailing spaces!

def lambda_handler(event, context):
    try:
        # 1) List all objects in the bucket, without prefix
        resp = s3.list_objects_v2(Bucket=BUCKET_NAME)
        print("DEBUG: s3.list_objects_v2 response:", resp)

        if 'Contents' not in resp or len(resp['Contents']) == 0:
            return {
                "statusCode": 404,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "No files found in the bucket."})
            }

        # 2) Filter only files ending with ".json"
        json_files = [obj for obj in resp['Contents'] if obj['Key'].lower().endswith('.json')]
        print("DEBUG: JSON files found:", [j['Key'] for j in json_files])

        if not json_files:
            return {
                "statusCode": 404,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "No JSON files found in the bucket."})
            }

        # 3) Get the most recent one (based on LastModified)
        latest_obj = max(json_files, key=lambda x: x['LastModified'])
        s3_key = latest_obj['Key']
        print(f"DEBUG: JSON selected for loading: {s3_key}")

        # 4) Download that JSON file
        obj_resp = s3.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        profile_obj = json.loads(obj_resp['Body'].read().decode('utf-8'))
        print("DEBUG: JSON content read:", profile_obj)

        # 5) Return the JSON to the caller
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(profile_obj)
        }

    except ClientError as e:
        print(f"S3 CLIENT ERROR: {e}")
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Internal S3 error."})
        }

    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"DETAILED GENERIC ERROR:\n{error_msg}")
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": f"Internal server error: {str(e)}"})
        }
