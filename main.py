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

from nextleg_api import generate_image, get_status, upload_image

import zhipuai
from fastapi.responses import FileResponse
import aiofiles


app = FastAPI(docs_url="/docs")


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


# get child personality text & similar celeb text & image
@app.get("/child_personality/{parent_name}")
def read_personality(parent_name):
    personality = "非常可爱的小孩"
    response = {
        "child_id": uuid.uuid4(),
        "parent_name": parent_name,
        "personality": personality,
    }

    return response


def get_similar_celeb():
    return


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
        return {"code": 200, "result": "{ADDRESS}/images/" + filename, "msg": "success"}
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


async def download_and_save_image(image_url: str, image_filename: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(image_url)

    if response.status_code != 200:
        return None

    image_path = os.path.join(images_directory, image_filename)

    with open(image_path, "wb") as f:
        f.write(response.content)

    return image_path


def url_to_filepath(url):
    filename = url.split("/")[-1]  # Extracts '20231014095827-ic_woman.png' from the URL
    filepath = os.path.join(images_directory, filename)  # Joins with directory path
    return filepath


@app.post("/merge")
async def merge_image(user_url: str, demo_img_url: str):
    # 1. Upload the images
    url1 = upload_image(url_to_filepath(user_url))
    url2 = upload_image(url_to_filepath(demo_img_url))

    # Check if images were uploaded successfully
    if not url1 or not url2:
        raise HTTPException(status_code=400, detail="Image upload failed!")

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
            images = status["response"]["imageUrls"]
            break
        await asyncio.sleep(5)
    else:  # this block executes when the while loop exits normally (non-break)
        raise HTTPException(status_code=400, detail="Image generation timed out!")

    # Download and save the merged image locally
    merged_filename = f"{uuid.uuid4()}.jpg"
    await download_and_save_image(merged_url, merged_filename)

    # Download and save additional images locally
    local_image_urls = []
    for img_url in images:
        filename = f"{uuid.uuid4()}.jpg"
        await download_and_save_image(img_url, filename)
        local_image_urls.append(f"{ADDRESS}/images/{filename}")

    return {
        "code": 200,
        "images": local_image_urls,
        "merged_url": f"{ADDRESS}/images/{merged_filename}",
        "msg": "success",
    }
