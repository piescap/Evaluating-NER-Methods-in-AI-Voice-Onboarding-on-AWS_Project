
import boto3
import base64
import uuid
import json

s3 = boto3.client('s3')
transcribe = boto3.client('transcribe')

AUDIO_BUCKET = 'file-audio-onboarding'
TRANSCRIBE_OUTPUT_BUCKET = 'file-transcribe-onboarding'
OUTPUT_PROFILE_BUCKET = 'file-output-profilo-onboarding'  # <— bucket to empty at the’start


def empty_bucket(bucket_name: str):
    """
    Completely empties the specified bucket.
    Handles both buckets without versioning and with versioning (Versions + DeleteMarkers).
    """
    # 1) Delete "current" objects
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket_name):
        objects = [{'Key': obj['Key']} for obj in page.get('Contents', [])]
        for i in range(0, len(objects), 1000):
            s3.delete_objects(
                Bucket=bucket_name,
                Delete={'Objects': objects[i:i+1000], 'Quiet': True}
            )

    # 2) Delete any versions and delete markers (if the bucket has versioning)
    paginator_ver = s3.get_paginator('list_object_versions')
    for page in paginator_ver.paginate(Bucket=bucket_name):
        to_delete = []
        for v in page.get('Versions', []):
            to_delete.append({'Key': v['Key'], 'VersionId': v['VersionId']})
        for dm in page.get('DeleteMarkers', []):
            to_delete.append({'Key': dm['Key'], 'VersionId': dm['VersionId']})

        for i in range(0, len(to_delete), 1000):
            s3.delete_objects(
                Bucket=bucket_name,
                Delete={'Objects': to_delete[i:i+1000], 'Quiet': True}
            )


def lambda_handler(event, context):
    try:
        print("Event received:", event)  # Debug

        # **EMPTY THE BUCKET AT THE START**
        empty_bucket(OUTPUT_PROFILE_BUCKET)

        # Decode the request body and the audio from base64
        body = json.loads(event['body'])
        audio_base64 = body['audio']
        audio_data = base64.b64decode(audio_base64)

        # Save the audio to S3
        filename = f"{uuid.uuid4()}.webm"
        s3.put_object(
            Bucket=AUDIO_BUCKET,
            Key=filename,
            Body=audio_data,
            ContentType='audio/webm'
        )

        # Create S3 URI and set the job name
        s3_uri = f"s3://{AUDIO_BUCKET}/{filename}"
        job_name = context.aws_request_id  # Unique name

        # Start the Transcribe job
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": s3_uri},
            MediaFormat="webm",
            OutputBucketName=TRANSCRIBE_OUTPUT_BUCKET,
            LanguageCode="it-IT"
        )

        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Methods": "*"
            },
            "body": json.dumps({
                "message": f"Bucket '{OUTPUT_PROFILE_BUCKET}' emptied. Audio uploaded and Transcribe job started: {filename}",
                "transcribeJobName": job_name
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Methods": "*"
            },
            "body": json.dumps({"error": str(e)})
        }
