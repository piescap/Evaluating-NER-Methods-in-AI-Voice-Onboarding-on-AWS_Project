import json
import boto3
import requests

# Initialize clients
s3 = boto3.client("s3")


DEEPSEEK_API_KEY = ""
DEEPSEEK_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek/deepseek-r1:free"


def lambda_handler(event, context):
    try:
        # Extract info from the S3 trigger
        record = event["Records"][0]
        bucket_name = record["s3"]["bucket"]["name"]
        file_name = record["s3"]["object"]["key"]

        # Ignore files that are not .json
        if not file_name.lower().endswith(".json"):
            print(f"Ignored non-JSON file: {file_name}")
            return {"statusCode": 200, "body": "File ignored"}

        # Download the JSON file from S3
        response = s3.get_object(Bucket=bucket_name, Key=file_name)
        content = response['Body'].read().decode('utf-8')
        data = json.loads(content)

        # Extract the transcription
        try:
            testo = data["results"]["transcripts"][0]["transcript"]
        except (KeyError, IndexError):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Transcription not found in the JSON file"})
            }

        # Build the prompt for Deepseek (same entity extraction logic)
        prompt = f"""Estrai le seguenti entità dal testo: NOME, ETA (in numero), GENERE (comprendilo dal nome), PERS (tratti di personalità nell'ordine 'Altruista', 'Flessibile', 'Vulnerabile', 'Istintivə', 'Estroversə'), LIVELLI_PERS (definisci ogni personalità con un valore da 1 a 3  (poco,abbastanza,molto) se menzionato e basta 2 mentre se non menzionato 0 nell'ordine 'Altruista', 'Flessibile', 'Vulnerabile', 'Istintivə', 'Estroversə') CITTA, PROFESSIONE, ALTEZZA (in formato 0.00), HOBBY (attività di svago o passioni), INTERESSE (il tipo di persona cercata), RANGEETA.

Testo:
"{testo}"

Rispondi **solo** con il contenuto JSON, **senza usare blocchi Markdown**, senza spiegazioni o testi aggiuntivi. Il formato deve essere esattamente questo:
{{
  "NOME": "...",
  "ETA": "...",
  "GENERE": "...",
  "PERS": ["...", "..."],
  "LIVELLI_PERS": ["...", "..."],
  "CITTA": "...",
  "PROFESSIONE": "...",
  "ALTEZZA": "...",
  "HOBBY": ["..."],
  "INTERESSE": "...",
  "RANGEETA": {{
    "min": "...",
    "max": "..."
  }}
}}"""

        # Prepare the HTTPS request to OpenRouter/Deepseek
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

        # Make the call to Deepseek (set a maximum timeout, e.g. 30s)
        api_response = requests.post(
            url=DEEPSEEK_ENDPOINT,
            headers=headers,
            data=json.dumps(payload),
            timeout=20
        )

        print("OpenRouter raw response:", api_response.text)  ############

        # If HTTP status is not OK, raise an exception
        api_response.raise_for_status()

        # Extract the response text from Deepseek
        body_json = api_response.json()
        # Deepseek/Chat Completions typically returns:
        #   body_json["choices"][0]["message"]["content"]
        deepseek_output_text = body_json["choices"][0]["message"]["content"].strip()

        # Try to convert the output to JSON
        try:
            entita = json.loads(deepseek_output_text)
        except json.JSONDecodeError:
            entita = {
                "error": "Output is not in valid JSON format",
                "raw_output": deepseek_output_text
            }

        # Save the output to the final bucket (you can change the name if needed)
        output_bucket = "file-output-profilo-onboarding"
        output_key = file_name.replace(".json", "_deepseek.json")
        s3.put_object(
            Bucket=output_bucket,
            Key=output_key,
            Body=json.dumps(entita, ensure_ascii=False),
            ContentType="application/json"
        )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "analyzed_file": file_name,
                "output_saved_in": f"s3://{output_bucket}/{output_key}",
                "entita": entita
            }, ensure_ascii=False)
        }

    except requests.exceptions.Timeout as e:
        return {
            "statusCode": 504,
            "body": json.dumps({"error": "Timeout during call to Deepseek", "details": str(e)})
        }
    except requests.exceptions.RequestException as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "HTTP error during call to Deepseek",
                "details": str(e),
                "response_text": getattr(e.response, "text", None)
            })
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"generic_error": str(e)})
        }
