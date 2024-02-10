# Python イメージを取得
# https://hub.docker.com/_/python
FROM python:3.10-slim
  
# ローカルコードをコンテナイメージに複製
COPY . /app
  
# 作業ディレクトリ指定
WORKDIR /app
  
# 依存関係のインストール
RUN pip install --no-cache-dir -r requirements.txt

# コンテナがリッスンするポート指定
EXPOSE 7860
  
# コンテナ起動時のコマンド
CMD ["python", "app.py"]