import asyncio
import uuid
from typing import Union
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
import json
from typing import Optional
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
import os
import random

import httpx
from pydantic import BaseModel

from nextleg_api import generate_image, get_status, upload_image

import zhipuai
from fastapi.responses import FileResponse
from PIL import Image
from io import BytesIO
from pymilvus import MilvusClient

import requests
from typing import Dict
import hashlib
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException
from enum import Enum


BACKUP_FILE = "backup_img.json"
backup_lock = asyncio.Lock()

# Load BACKUP_IMG from a file
try:
    with open(BACKUP_FILE, 'r') as file:
        BACKUP_IMG = json.load(file)
except (FileNotFoundError, json.JSONDecodeError):
    BACKUP_IMG = []

MAX_BACKUP_IMG_SIZE = 100

async def manage_and_save_backup_img(new_data):
    """
    Manages the BACKUP_IMG list: appending new data, ensuring the data doesn't exceed 
    the maximum size, and saves it to a file.
    
    Parameters:
        new_data (dict): New data to append to BACKUP_IMG
    
    Returns:
        None
    """
    global BACKUP_IMG  # to modify the global variable
    
    # Add the new data to BACKUP_IMG
    BACKUP_IMG.append(new_data)
    
    # Ensure that BACKUP_IMG doesn't exceed the maximum size
    while len(BACKUP_IMG) > MAX_BACKUP_IMG_SIZE:
        # Randomly shuffle the list and remove an item
        random.shuffle(BACKUP_IMG)
        BACKUP_IMG.pop()
    
    # Save BACKUP_IMG to a file with a lock
    async with backup_lock:
        with open(BACKUP_FILE, 'w') as file:
            json.dump(BACKUP_IMG, file)


api_key = "2f782ccb712e4395ea69565ec3bd3d5d67c44ff4513fcb7e00b6da08ff151c670f85a4848813c67fc5e4a90329cd71cee8dcbc40"
milvus_uri = "https://in03-5cac29c7c5c6f18.api.gcp-us-west1.zillizcloud.com"
zhipuai.api_key = "1e987cc89e8fe21f963e913a0c3e6c30.f2uJtohLlyIc3fe0"

client = MilvusClient(uri=milvus_uri, token=api_key)
child_personality_traits = [
    "活泼",
    "好奇",
    "天真",
    "有创造力",
    "勤奋",
    "敢于尝试",
    "乐观",
    "独立",
    "友善",
    "坚韧",
    "戏剧性的",
    "自由的",
    "有责任感的",
]

child_vocation = [
    "诗人",
    "作家",
    "科学家",
    "企业家",
    "音乐家",
    "影星",
]

child_cost = [
    "300",
    "400",
    "500",
    "600",
    "700",
    "800",
    "900",
    "1000",
]


def get_description():
    chosen_traits = random.sample(child_personality_traits, 3)
    chosen_vocation = random.sample(child_vocation, 1)
    chosen_cost = random.sample(child_cost, 1)
    traits = ",".join(chosen_traits)
    vocation = ",".join(chosen_vocation)
    cost = ",".join(chosen_cost)
    
    print("\ntraits:")
    print(traits+","+vocation)
    embedding_response = zhipuai.model_api.invoke(
        model="text_embedding",
        prompt=traits,
    )
    print("\nembedding_response:")
    # print(embedding_response)
    embedding = embedding_response["data"]["embedding"]
    search_response = client.search(
        collection_name="celebrity",
        data=[embedding],
        limit=2,
        output_fields=["name"])[0]
    print("\nsearch_response:")
    # print(search_response)

    ids = [resp["id"] for _, resp in enumerate(search_response)]
    print("\nids:")
    print(ids)
    get_response = client.get(
        collection_name="celebrity", ids=ids)
    print("\nget_response:")
    # print(get_response)

    joined_description = ",".join([resp["description"] for _, resp in enumerate(get_response)])
    name = ",".join([resp["name"] for _, resp in enumerate(get_response)])
    content = (f"use multiple contexts in <context></context> quote to generate response:"
               f"<context>{joined_description}</context>"
               f"strictly follow the format example, with header in the <context></context> quote"
               f"<context>性格兴趣：</context> 小时候的她，活泼且才华洋溢，怀揣音乐梦，她乐观的性格引领未来之路。\n\n"
               f"<context>养育成本：</context> 未来10年，你需要为孩子的音乐教育预算500万！"
               f"生成以{traits}为性格,{name}为偶像的孩子的两句短话，并以\n\n分割：")

    print("\ncontent:")
    print(content)
    response = zhipuai.model_api.invoke(
        model="chatglm_pro",
        prompt=[{"role": "user", "content": content}],
        top_p=0.7,
        temperature=0.9,
    )
    print("\nresponse:")
    # print(response)
    content = response["data"]["choices"][0]["content"]
    content = content.replace("<context>", "").replace("</context>", "")
    content = content.replace("\\\n", "\n").replace("\\n", "\n")
    content = content.replace("\"", "")
    content = content.replace("她", "TA").replace("他", "TA")
    content = content.replace("500", cost)
    
    return content



app = FastAPI(docs_url="/xagixdoc")


from fastapi.middleware.cors import CORSMiddleware


# 以下是 CORS 中间件设置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境下应为实际的源地址
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有请求头
)


@app.get("/")
def read_root():
    zhipuai.api_key = "1e987cc89e8fe21f963e913a0c3e6c30.f2uJtohLlyIc3fe0"
    response = zhipuai.model_api.invoke(
        model="chatglm_pro",
        prompt=[{"role": "user", "content": "一步步想，迪丽热巴的性格人设"}],
        top_p=0.7,
        temperature=0.9,
    )
    return {"Hello": "World", "response": response}


# get child content
@app.get("/get_content")
def get_content():
    response = {
        "content": get_description()
    }

    return response


def generate_sign(data: Dict[str, str], key: str) -> str:
    # Remove sign, sign_type and empty values
    valid_data = {k: v for k, v in data.items() if k not in ("sign", "sign_type") and v is not None}

    # Sort the data by key
    sorted_data = dict(sorted(valid_data.items()))

    # Concatenate the sorted data into a single string with the format a=b&c=d
    data_string = "&".join(f"{k}={v}" for k, v in sorted_data.items())

    # Append the key
    data_string += key

    # Create the MD5 signature
    md5 = hashlib.md5()
    md5.update(data_string.encode())
    sign = md5.hexdigest().lower()  # Ensure the result is in lowercase

    return sign


def generate_out_trade_no(img_url: str) -> str:
    # Implement your trade number generation here
    return img_url


TEST_KEY = "WBZHZWBeheKhWZcKuGRlb8lKWzwCWUeH"
TEST_PID = 1000


@app.post("/generate_payment_qrcode")
def generate_payment_qrcode(img_url: str, price: str):
    pid = TEST_PID  # Your merchant ID
    out_trade_no = generate_out_trade_no(img_url)
    notify_url = "http://18.163.103.199:8000/notification_endpoint"
    return_url = "http://18.163.103.199:8000/return_url.php"
    name = "Test"  # Or any product name
    clientip = "127.0.0.1"  # Or any suitable client IP retrieval
    device = "mobile"  # Or any device determining mechanism string
    sign_type = "MD5"

    # Prepare data for sign generation
    data = {
        'pid': pid,
        'type': 'wxpay',
        'out_trade_no': out_trade_no,
        'notify_url': notify_url,
        'return_url': return_url,
        'name': name,
        'money': "0.01",
        'clientip': clientip,
        'device': device,
        'sign_type': sign_type
    }

    # Generate sign and add it to data
    data['sign'] = generate_sign(data, key=TEST_KEY)

    # Make the payment request
    response = requests.post("https://api.payqqpay.cn/mapi.php", data=data)
    print("response:", response.content)
    json.loads(response.content)

    # Ensure the request was successful
    response.raise_for_status()

    # Retrieve the payment URL
    qrcode = json.loads(response.content)['qrcode']
    trade_no = json.loads(response.content)['trade_no']

    return {
        "trade_no": trade_no,
        "qrcode": qrcode
    }


@app.get("/notification_endpoint")
async def process_notification(notify_request: NotifyRequest):
    print("notify_request:", notify_request)
    # From here, you can process the notification.
    if notify_request.trade_status == TradeStatus.trade_success:
        # Process success payment notification
        # For example, update your database record for the order using `notify_request.out_trade_no`
        pass
    else:
        # Handle other payment states
        pass

    return {"detail": "Notification processed"}



images_directory = "user-imgs"
ADDRESS = "http://18.163.103.199:8000"


@app.get("/images/{filename}")
async def read_image(filename: str):
    file_path = os.path.join(images_directory, filename)

    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="image/jpeg")
    else:
        raise HTTPException(status_code=400, detail="Image not found.")


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}


@app.post("/uploadfiles")
async def create_upload_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()  # read file content

        timestamp = datetime.now()  # get current time
        filename = f"{timestamp.strftime('%Y%m%d%H%M%S')}-{file.filename}"  # append timestamp to filename

        with open(os.path.join(images_directory, filename), "wb") as fp:
            fp.write(contents)
        return {"code": 200, "result": f"{ADDRESS}/images/" + filename, "msg": "success"}
    except Exception as e:
        print(f"Error: {e}")  # print out the error
        raise HTTPException(status_code=400, detail="File upload failed.")


# merge file
# @app.post("/merge")
# def merge_image(user_url: str, parent_id: int):

#     demo_img_url = "http://121.40.29.191:8000/images/20231014095827-ic_woman.png"
#     demo_imgs = [demo_img_url]*4
#     demo_description = "小杰是个充满好奇心的孩子，他总是活力充沛、充满热情地探索世界。他找到微观世界中隐藏的秘密，因为他总是会细心地观察、思考。他观察蚂蚁如何建立蚁巢，他细心地记下他们的轨迹和行为。这些特质使得小杰在成长过程中学会了独立解决问题，并从中获取快乐。"
#     print(f"user_url: {user_url}, parent_id: {parent_id}")
#     return { "code": 200, "description": demo_description,
#             "images": demo_imgs,
#             "merged_url": demo_img_url, "msg": "success" }



async def download_and_save_image(image_url: str):
    print('download_and_save_image: ', image_url)
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(image_url)
    if response.status_code != 200:
        return None
    
    # Load image with Pillow and convert to JPEG
    try:
        image = Image.open(BytesIO(response.content))
        # Convert image to RGB if it's in a different mode
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Define dimensions for cropping
        width, height = image.size
        left = 0
        top = 0
        right = width // 2
        bottom = height // 2

        # Create crop coordinates for each sub-image
        coordinates = [
            (left, top, right, bottom),  # top-left
            (right, top, width, bottom),  # top-right
            (left, bottom, right, height),  # bottom-left
            (right, bottom, width, height)  # bottom-right
        ]

        image_filenames = []

        # Crop and save each sub-image
        for i, coord in enumerate(coordinates):
            cropped_image = image.crop(coord)
            image_filename = f"{uuid.uuid4()}.jpg"
            image_path = os.path.join(images_directory, image_filename)
            cropped_image.save(image_path, "JPEG")
            image_filenames.append(f"{ADDRESS}/images/{image_filename}")

        # Save the original image
        original_filename = f"{uuid.uuid4()}.jpg"
        original_path = os.path.join(images_directory, original_filename)
        image.save(original_path, "JPEG")

        return {"original": original_filename, "cropped": image_filenames}

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None

def url_to_filepath(url):
    filename = url.split("/")[-1]  # Extracts '20231014095827-ic_woman.png' from the URL
    filepath = os.path.join(images_directory, filename)  # Joins with directory path
    return filepath


class ImageUrls(BaseModel):
    user_url: str
    demo_img_url: str


@app.post("/merge")
async def merge_image(user_url: str, demo_img_url: str):

    result_data = random.choice(BACKUP_IMG)
    async def merge_process():
        # 1. Upload the images
        url1 = upload_image(url_to_filepath(user_url))
        url2 = upload_image(url_to_filepath(demo_img_url))

        # 2. Generate an image with the two uploaded images and a prompt
        prompt_message = "4 years old little baby, cute, child of {url1} and {url2} --v 5"
        res = await generate_image(url1, url2, prompt_message)
        id = res["messageId"]
        print(res)

        # 3. Check the status every 5 seconds, for up to 2 minutes
        timeout = timedelta(minutes=2)
        start_time = datetime.now()

        while datetime.now() - start_time < timeout:
            status = await get_status(id)
            print(status)
            if status["progress"] == 100:
                merged_url = status["response"]["imageUrl"]
                break
            await asyncio.sleep(5)

        # Download and save the merged image locally
        merged_filename = await download_and_save_image(merged_url)
        result_data = {
            "images": merged_filename['cropped'],
            "merged_url": f"{ADDRESS}/images/{merged_filename['original']}",
        }
        return result_data

    try:
        result_data = await asyncio.wait_for(merge_process(), timeout=80)
        await manage_and_save_backup_img(result_data)
    except asyncio.TimeoutError:
        print("Error: The merging process took too long!")
    except Exception as e:
        print(f"Error: {str(e)}")

    description = (f"性格兴趣： 小时候的她，活泼且才华洋溢，怀揣音乐梦，她乐观的性格引领未来之路。"
                   f"养育成本： 未来10年，你需要为孩子的音乐教育预算500万！")
    try:
        description = get_description()
    except Exception as e:
        print(f"An error occurred: {e}")

    print('result: ----', description, result_data)
    return {
        "content": description,
        "code": 200,
        "images": result_data['images'],
        "merged_url": result_data['merged_url'],
        "msg": "success",
    }
