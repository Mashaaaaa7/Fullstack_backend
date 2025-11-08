from transformers import T5ForConditionalGeneration, T5Tokenizer
import pdfplumber
import torch
import os


class QAGenerator:
    def __init__(self, model_path: str = None):
        """
        Инициализация генератора вопросов

        Args:
            model_path: Путь к обученной модели (если None - используется базовая)
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        if model_path and os.path.exists(model_path):
            print(f"📦 Загрузка обученной модели из {model_path}")
            self.tokenizer = T5Tokenizer.from_pretrained(model_path)
            self.model = T5ForConditionalGeneration.from_pretrained(model_path).to(self.device)
            print("✅ Обученная модель загружена!")
        else:
            print("📦 Загрузка базовой модели...")
            model_name = "cointegrated/rut5-base-multitask"
            self.tokenizer = T5Tokenizer.from_pretrained(model_name)
            self.model = T5ForConditionalGeneration.from_pretrained(model_name).to(self.device)
            print("✅ Базовая модель загружена!")

    def extract_pdf_text(self, file_path: str) -> str:
        """Извлекает текст из PDF"""
        text = ''
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + '\n'
        return text

    def generate_question(self, context: str) -> str:
        """Генерирует вопрос из контекста"""
        input_text = f"generate question: {context}"

        inputs = self.tokenizer(
            input_text,
            return_tensors="pt",
            max_length=512,
            truncation=True
        ).to(self.device)

        outputs = self.model.generate(
            **inputs,
            max_length=64,
            num_beams=4,
            early_stopping=True,
            temperature=0.7
        )

        question = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return question

    def process_pdf(self, file_path: str, max_cards: int = 10) -> list:
        """Главный метод: PDF → карточки"""
        # Извлекаем текст
        text = self.extract_pdf_text(file_path)

        if not text.strip():
            return []

        # Разбиваем на части
        chunk_size = 500
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

        # Генерируем карточки
        cards = []
        for idx, chunk in enumerate(chunks[:max_cards]):
            try:
                question = self.generate_question(chunk)
                cards.append({
                    'id': idx,
                    'question': question,
                    'answer': chunk[:200],  # Первые 200 символов как ответ
                    'source': chunk[:50]
                })
            except Exception as e:
                print(f"❌ Ошибка генерации карточки {idx}: {e}")
                continue

        return cards
