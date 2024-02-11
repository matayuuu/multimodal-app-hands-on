import base64
import logging
import os
import sys
  
import google.cloud.logging
from google.cloud import storage
import gradio as gr
import PIL.Image
import vertexai
from vertexai.preview.generative_models import GenerativeModel, Part, GenerationConfig, GenerationResponse
  
  
PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION")
FILE_BUCKET_NAME = os.environ.get("FILE_BUCKET_NAME")
SUPPORTED_IMAGE_EXTENSIONS = [
    "png",
    "jpeg",
    "jpg",
]
SUPPORTED_VIDEO_EXTENSIONS = [
    "mp4",
    "mov",
    "mpeg",
    "mpg",
    "avi",
    "wmv",
    "mpegps",
    "flv",
]
ALL_SUPPORTED_EXTENSIONS = set(SUPPORTED_IMAGE_EXTENSIONS + SUPPORTED_VIDEO_EXTENSIONS)
MAX_PROMPT_SIZE_MB = float(os.environ.get("MAX_PROMPT_SIZE_MB"))
  

# 標準 Logger の設定
logging.basicConfig(
        format = "[%(asctime)s][%(levelname)s] %(message)s",
        level = logging.DEBUG # ログレベルをデバックから取得するように設定
    )
logger = logging.getLogger()
  

# 各サービスの初期化
try:
    logging_client = google.cloud.logging.Client()
    logging_client.setup_logging()
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    storage_client = storage.Client(project=PROJECT_ID)
    txt_model = GenerativeModel("gemini-pro")
    multimodal_model = GenerativeModel("gemini-pro-vision")
except Exception as e:
    logger.error(f"An error occurred during the initialization of one or more services: {e}")
  

# ファイルを Base64 にエンコード
def file_to_base64(file_path: str) -> str:
    try:
        with open(file_path, "rb") as file:
            return base64.b64encode(file.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"An error occurred during file_to_base64 func.: {e}")
  
  
# ファイルの拡張子を取得
def get_extension(file_path: str) -> str:
    if "." not in file_path:
        logger.error(f"Invalid file path. : {file_path}")
    
    extension = file_path.split(".")[-1].lower()
    if not extension:
        logger.error(f"File has no extension. : {file_path}")
    
    return extension
  
  
# 画像/動画ファイルを Cloud Storage にアップロード
def file_upload_gsc(file_bucket_name: str, source_file_path: str) -> str:
    try:
        bucket = storage_client.bucket(file_bucket_name)
  
        # ファイルの名前を取得
        destination_blob_name = os.path.basename(source_file_path)
  
        # ファイルをアップロード
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_path)
        return f"gs://{file_bucket_name}/{destination_blob_name}"
  
    except Exception as e:
        logger.error(f"Error uploading to Cloud Storage: {e}")
  
  
# extension がサポートされているか判定
def is_extension(extension: str) -> bool:
    return extension in ALL_SUPPORTED_EXTENSIONS
  
  
# mime_type を取得
def create_mime_type(extension: str) -> str:
    # サポートされた画像形式の場合
    if extension in SUPPORTED_IMAGE_EXTENSIONS:
        return "image/jpeg" if extension in ["jpg", "jpeg"] else f"image/{extension}"
  
    # サポートされた動画形式の場合
    elif extension in SUPPORTED_VIDEO_EXTENSIONS:
        return f"video/{extension}"
    
    # サポートされていない拡張子の場合
    else:
        logger.error(f"Not supported mime_type for extension: {extension}")
  
  
# プロンプトサイズの計算
def calculate_prompt_size_mb(text: str, file_path: str) -> float:
    try:
        # テキストサイズをバイト単位で取得
        text_size_bytes = sys.getsizeof(text)
    
        # ファイルサイズをバイト単位で取得
        file_size_bytes = os.path.getsize(file_path)
    
        # バイトからメガバイトに単位変換
        prompt_size_mb = (text_size_bytes + file_size_bytes) / 1048576
    except Exception as e:
        logger.error(f"Error calculating prompt size: {e}")
  
    return prompt_size_mb
  

# ユーザーのクエリメッセージを作成
def query_message(history: str, txt: str, image: str, video: str) -> str:
    try:
        # ユーザーのクエリがテキストのみの場合
        if not (image or video):
            history += [(txt,None)]
    
        # ユーザーのクエリに画像が含まれる場合
        if image:
            prompt_size_mb = calculate_prompt_size_mb(text=None, file_path=image)
            
            # 画像サイズが上限を超えた場合
            if prompt_size_mb > MAX_PROMPT_SIZE_MB:
                history += [(f"[This Image is not display] {txt}", None)]
            else:
                image_extension = get_extension(image)
                base64 = file_to_base64(image)
                data_url = f"data:image/{image_extension};base64,{base64}"
                image_html = f'<img src="{data_url}" alt="Uploaded image">'
                history += [(f"{image_html} {txt}", None)]
    
        # ユーザーのクエリに動画が含まれる場合
        if video:
            prompt_size_mb = calculate_prompt_size_mb(text=None, file_path=video)
  
            # 動画サイズが上限を超えた場合
            if prompt_size_mb > MAX_PROMPT_SIZE_MB:
                history += [(f"[This video is not display] {txt}", None)]
            else:
                video_extension = get_extension(video)
                base64 = file_to_base64(video)
                data_url = f"data:video/{video_extension};base64,{base64}"
                video_html = f'<video controls><source src="{data_url}" type="video/{video_extension}"></video>'
                history += [(f"{video_html} {txt}", None)]
    except Exception as e:
        logger.error(f"Error processing query message: {e}")
  
    return history
    
  
# Gemini からの出力を取得
def gemini_response(
    history: str, 
    text: str, 
    image: str, 
    video: str, 
    temperature: float,
    max_output_tokens: int,
    top_k: int,
    top_p: float, 
) -> str:
    try:
        # テキストが未入力の場合
        if not text:
            response = "テキストを入力して下さい。"
            history += [(None,response)]
  
        # テキストのみの場合
        elif not (image or video):
            # Gemini Pro にリクエストを送信
            response = txt_model.generate_content(
                contents=text,
                generation_config=GenerationConfig(
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    max_output_tokens=max_output_tokens
                )
            )
  
            history += [(None,response.text)]
      
        # 画像と動画の両方が入力された場合
        elif image and video:
            response = "1度に画像と動画を含めることはサポートされていません。"
            
            history += [(None,response)]
  
        else:        
            # ファイルパスを取得
            file_path = image or video
  
            # プロンプトサイズを取得
            prompt_size_mb = calculate_prompt_size_mb(text=text, file_path=file_path)
  
            # プロンプトサイズが上限を超えた時
            if prompt_size_mb > MAX_PROMPT_SIZE_MB:
                response = f"画像/動画とテキストを含むプロンプトサイズは{MAX_PROMPT_SIZE_MB}MB未満として下さい。現在のプロンプトサイズは{round(prompt_size_mb, 1)}MBです。"
        
                history += [(None,response)]
  
            else:
                # ファイルの拡張子を取得
                extension = get_extension(file_path=file_path)
    
                # サポートされている extension の場合
                if is_extension(extension):
  
                    # 画像/動画ファイルを Cloud Storage にアップロード
                    gcs_url = file_upload_gsc(file_bucket_name=FILE_BUCKET_NAME, source_file_path=file_path)
  
                    # mime_type を取得
                    mime_type = create_mime_type(extension)
                    
                    # Gemini Pro Vision にリクエストを送信
                    file = Part.from_uri(uri=gcs_url, mime_type=mime_type)
                    response = multimodal_model.generate_content(
                        contents=[file, text],
                        generation_config=GenerationConfig(
                            temperature=temperature,
                            top_p=top_p,
                            top_k=top_k,
                            max_output_tokens=max_output_tokens
                        )
                    )
        
                    history += [(None,response.text)]
  
                else:
                    support_image_extensions_str = ", ".join(SUPPORTED_IMAGE_EXTENSIONS)
                    support_video_extensions_str = ", ".join(SUPPORTED_VIDEO_EXTENSIONS)
                    response = f"サポートされている形式について、画像の場合は {support_image_extensions_str} で、動画の場合は {support_video_extensions_str} です。"
                    
                    history += [(None,response)]
    
    except Exception as e:
        logger.error(f"Error during Gemini response generation: {e}")
  
    return history
  
  
# Gradio インターフェース
with gr.Blocks() as app:
    # 画面の各コンポーネント
    with gr.Row():
        with gr.Column():
            chatbot = gr.Chatbot(scale = 2)
        with gr.Column():
            image_box = gr.Image(type="filepath", sources=["upload"], scale = 1)
            video_box = gr.Video(sources=["upload"], scale = 1)
    with gr.Row():
        with gr.Column():
            text_box = gr.Textbox(
                    placeholder="テキストを入力して下さい。",
                    container=False,
                    scale = 2
                )
        with gr.Column():
            with gr.Row():
                temperature = gr.Slider(label="Temperature", minimum=0, maximum=1, step=0.1, value=0.4, interactive=True)
                max_output_tokens = gr.Slider(label="Max Output Token", minimum=1, maximum=2048, step=1, value=1024, interactive=True)
            with gr.Row():
                top_k = gr.Slider(label="Top-K", minimum=1, maximum=40, step=1, value=32, interactive=True)
                top_p = gr.Slider(label="Top-P", minimum=0.1, maximum=1, step=0.1, value=1, interactive=True)
    with gr.Row():
        btn_refresh = gr.Button(value="Refresh")
        btn_submit = gr.Button(value="Submit")
  
   
    # Submitボタンが押下されたときの処理
    btn_submit.click(
        query_message,
        [chatbot, text_box, image_box, video_box],
        chatbot
    ).then(
        gemini_response,
        [chatbot, text_box, image_box, video_box, temperature, max_output_tokens, top_k, top_p],
        chatbot
    )
  
    # Refreshボタンが押下されたときの処理
    btn_refresh.click(None, js="window.location.reload()")
    
app.launch(server_name="0.0.0.0", server_port=7860)