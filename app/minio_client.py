import os
from minio import Minio
from minio.error import S3Error
import uuid
from fastapi import UploadFile, HTTPException
import logging
from typing import Optional

# Настройки из переменных окружения
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET_PDF = os.getenv("MINIO_BUCKET_PDF", "pdf-files")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)


def ensure_bucket(bucket: str):
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logging.info(f"Bucket '{bucket}' created")


ensure_bucket(MINIO_BUCKET_PDF)


def generate_file_key(original_filename: str) -> str:
    ext = os.path.splitext(original_filename)[1]
    return f"{uuid.uuid4().hex}{ext}"


async def upload_file_to_minio(file: UploadFile, bucket: str, file_key: Optional[str] = None) -> str:
    if file_key is None:
        file_key = generate_file_key(file.filename)

    # Читаем содержимое (осторожно с большими файлами!)
    file_data = await file.read()
    file_size = len(file_data)
    content_type = file.content_type or "application/octet-stream"

    try:
        client.put_object(
            bucket_name=bucket,
            object_name=file_key,
            data=file_data,
            length=file_size,
            content_type=content_type
        )
        return file_key
    except S3Error as e:
        logging.error(f"MinIO upload error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload file to storage")
    finally:
        await file.close()


def delete_file_from_minio(bucket: str, file_key: str):
    try:
        client.remove_object(bucket, file_key)
    except S3Error as e:
        logging.error(f"MinIO delete error: {e}")


def generate_presigned_url(bucket: str, file_key: str, expires: int = 3600) -> str:
    try:
        url = client.presigned_get_object(bucket, file_key, expires=expires)
        return url
    except S3Error as e:
        logging.error(f"MinIO presigned URL error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate download link")