import os
import firebase_admin
from firebase_admin import credentials,messaging

key_path = os.getenv("FIREBASE_KEY_PATH")

cred = credentials.Certificate(key_path)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)


def send_push(token: str, title: str, body: str):
    """푸시알림 보내는 함수"""
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        data={
            "title": title,
            "body": body
        },
        token=token,
        android=messaging.AndroidConfig(
            priority="high"
        )
    )
    result = messaging.send(message)
    print("FCM 결과:", result)
