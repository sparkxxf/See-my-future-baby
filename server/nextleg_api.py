import httpx
import requests
import json
import uuid

TOKEN = '45875a2f-f1dc-499f-b5d2-b26457a9511e'
                
import boto3, os
from botocore.exceptions import NoCredentialsError

BUCKET_NAME = 'mantastore'

def upload_image(image_path):
    s3 = boto3.client('s3')

    # Determine content type based on file extension
    content_type = ''
    if image_path.endswith('.jpg') or image_path.endswith('.jpeg'):
        content_type = 'image/jpeg'

    elif image_path.endswith('.png'):
        content_type = 'image/png'
    # Add more file types as needed...

    # Generate a unique UUID name for the image
    unique_name = f"{uuid.uuid4()}.jpg" if content_type == "image/jpeg" else f"{uuid.uuid4()}.png"
    s3_key = f'hack/{unique_name}'

    try:
        with open(image_path, 'rb') as f:
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Body=f.read(),
                ContentType=content_type,
            )
        print(f"Upload Successful: {unique_name}")
        return f"https://store.mantachat.com/hack/{unique_name}"
    except FileNotFoundError:
        print("The file was not found")
        return None
    except NoCredentialsError:
        print("Credentials not available")
        return None


async def generate_image(url1, url2, prompt):
    payload = json.dumps({
        "msg": prompt.format(url1=url1, url2=url2),
        "ref": "",
        "webhookOverride": "",
        "ignorePrefilter": "false"
    })
    headers = {
        'Authorization': f'Bearer {TOKEN}',
        'Content-Type': 'application/json'
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post("https://api.thenextleg.io/v2/imagine", headers=headers, data=payload)
    return response.json()

async def get_status(id):
    headers = {'Authorization': f'Bearer {TOKEN}'}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"https://api.thenextleg.io/v2/message/{id}", headers=headers)
    return response.json()



