import requests
import json
import uuid

TOKEN = 'ec77ccfb-67fd-45ec-be6e-d07bed123430'
                

def generate_image(url1, url2, prompt):
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

	response = requests.request("POST", "https://api.thenextleg.io/v2/imagine", headers=headers, data=payload)
	# {
	#     "success": true,
	#     "messageId": "vhIxRWFETZDW5s093rvg",
	#     "createdAt": "2023-10-13T09:01:36.285Z"
	# }
	print(response.json())
	return response.json()


def get_status(id):

	headers = {
	  'Authorization': f'Bearer {TOKEN}',
	}

	response = requests.request("GET", f"https://api.thenextleg.io/v2/message/{id}", headers=headers)
	print(response.json())
	return response.json()

import boto3, os
from botocore.exceptions import NoCredentialsError

ACCESS_KEY = 'AKIA25EHHD56THMKKO2Y'
SECRET_KEY = '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'
BUCKET_NAME = 'mantastore'

def upload_image(image_path):
    s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY,
                      aws_secret_access_key=SECRET_KEY)

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



import time

def main(img1_path, img2_path, prompt_message):
    # 1. Upload the images
    url1 = upload_image(img1_path)
    url2 = upload_image(img2_path)

    # Check if images were uploaded successfully
    if not url1 or not url2:
        print("Image upload failed!")
        return

    # 2. Generate an image with the two uploaded images and a prompt
    res = generate_image(url1, url2, prompt_message)
    id = res['messageId']
    # 3. Check the status every 2 seconds
    while True:
        status = get_status(id)
        if status['progress'] == 100:
            print(f"Image URL: {status['response']['imageUrl']}")
            break
        time.sleep(5)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("Usage: python script_name.py <img1_path> <img2_path> <prompt_message>")
    else:
        main(sys.argv[1], sys.argv[2], sys.argv[3])

