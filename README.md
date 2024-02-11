# Multimodal app hands-on
## ディレクトリ階層
```
multimodal-app-hands-on
|--cloud_run
| |-- .dockerignore
| |-- app.py
| |-- Dockerfile
| `-- requirements.txt
`-- README.md
```

## 環境変数の設定
```sh
PROJECT_ID={プロジェクト ID}
TODAY=$(date +%Y%m%d)
SERVICE_NAME="multimodal-app"
REGION="asia-northeast1"
FILE_BUCKET_NAME="$PROJECT_ID-$SERVICE_NAME-$TODAY-hands-on"
AR_REPO="$SERVICE_NAME-$TODAY-hands-on"
SA_NAME="$SERVICE_NAME-sa"
MAX_PROMPT_SIZE_MB="4.0"
```

## gcloud SDK の設定変更
```sh
# 認証の初期化
gcloud auth login

# プロジェクト設定の変更
gcloud config set project $PROJECT_ID
```

## API の有効化
```sh
gcloud services enable --project=$PROJECT_ID  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  compute.googleapis.com \
  aiplatform.googleapis.com \
  iap.googleapis.com
```

## サービスアカウント作成
```sh
gcloud iam service-accounts create $SA_NAME
```

## Cloud Storage バケットの作成
```sh
gcloud storage buckets create gs://$FILE_BUCKET_NAME \
  --location=$REGION \
  --uniform-bucket-level-access \
  --public-access-prevention
```

## サービスアカウントへ権限付与
```sh
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
  
gcloud storage buckets add-iam-policy-binding gs://$FILE_BUCKET_NAME \
  --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.admin"
```

## Artifacts repositories 作成
```sh
gcloud artifacts repositories create $AR_REPO \
  --location=$REGION \
  --repository-format=Docker \
  --project=$PROJECT_ID
```

## イメージの作成＆更新
```sh
# ディレクトリの移動
cd multimodal-app-hands-on/cloud_run

# ビルド実行
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO/$SERVICE_NAME \
  --project=$PROJECT_ID 
```

## Cloud Run サービスデプロイ
```sh
gcloud run deploy $SERVICE_NAME --port 7860 \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO/$SERVICE_NAME \
  --allow-unauthenticated \
  --service-account=$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com \
  --region=$REGION \
  --set-env-vars=PROJECT_ID=$PROJECT_ID,LOCATION=$REGION,FILE_BUCKET_NAME=$FILE_BUCKET_NAME,MAX_PROMPT_SIZE_MB=$MAX_PROMPT_SIZE_MB \
  --memory=8Gi \
  --cpu=2 \
  --project=$PROJECT_ID
```

## お片付け
```sh
# Cloud Run サービス削除
gcloud run services delete $SERVICE_NAME \
  --region=$REGION \
  --project=$PROJECT_ID

# イメージの削除
gcloud artifacts repositories delete $AR_REPO \
  --location=$REGION \
  --project=$PROJECT_ID

# バケットの削除
gcloud storage rm -r gs://$FILE_BUCKET_NAME/**
gcloud storage buckets delete gs://$FILE_BUCKET_NAME

# サービスアカウントの削除
gcloud iam service-accounts delete $SA_NAME@$PROJECT_ID.iam.gserviceaccount.com
```