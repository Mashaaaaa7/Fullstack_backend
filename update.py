import requests

API_URL = "http://127.0.0.1:8000/api/auth/login"  # адрес сервера
EMAIL = "your_email@example.com"  # замени на свой email
PASSWORD = "your_password"        # замени на свой пароль

data = {
    "email": "mary200438@gmail.com",
    "password": "Mary2004"
}

try:
    response = requests.post(API_URL, json=data)
    if response.status_code == 200:
        resp_json = response.json()
        print("✅ Логин успешен!")
        print("Токен:", resp_json.get("access_token"))
        print("Полезные данные:", resp_json)
    else:
        print(f"❌ Ошибка: {response.status_code}")
        print(response.json())
except Exception as e:
    print("Ошибка при запросе:", e)
