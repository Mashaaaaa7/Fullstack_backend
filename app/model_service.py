# app/model_service.py

from transformers import T5ForConditionalGeneration, T5Tokenizer
import pdfplumber
import re


class QAGenerator:
    def __init__(self, model_path=None):
        if model_path:
            self.tokenizer = T5Tokenizer.from_pretrained(model_path)
            self.model = T5ForConditionalGeneration.from_pretrained(model_path)
        else:
            model_name = "cointegrated/rut5-base-multitask"
            self.tokenizer = T5Tokenizer.from_pretrained(model_name)
            self.model = T5ForConditionalGeneration.from_pretrained(model_name)

    def extract_text_from_pdf(self, pdf_path):
        """Извлекает текст из PDF"""
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text

    def split_into_chunks(self, text, max_length=300):
        """
        Разбивает текст на смысловые фрагменты (по предложениям)
        """
        # Удаляем лишние пробелы и переносы
        text = re.sub(r'\s+', ' ', text).strip()

        # Разбиваем по предложениям
        sentences = re.split(r'(?<=[.!?])\s+', text)

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= max_length:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def generate_question(self, context):
        """Генерирует вопрос из контекста"""
        input_text = f"generate question: {context}"

        inputs = self.tokenizer(
            input_text,
            max_length=512,
            truncation=True,
            return_tensors="pt"
        )

        outputs = self.model.generate(
            **inputs,
            max_length=100,  # ✅ Увеличил для полных вопросов
            num_beams=5,  # ✅ Лучшее качество
            temperature=0.7,  # ✅ Креативность
            do_sample=True,
            top_p=0.9
        )

        question = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Постобработка: убираем артефакты
        question = question.strip()
        if not question.endswith('?'):
            question += '?'

        return question

    def process_pdf(self, pdf_path, max_cards=10):
        """
        Обрабатывает PDF и генерирует карточки
        """
        text = self.extract_text_from_pdf(pdf_path)

        if not text or len(text) < 50:
            return []

        chunks = self.split_into_chunks(text, max_length=300)

        cards = []
        for i, chunk in enumerate(chunks[:max_cards]):
            if len(chunk) < 30:  # ✅ Пропускаем слишком короткие
                continue

            question = self.generate_question(chunk)

            # ✅ Ответ = первые 200 символов контекста
            answer = chunk[:200] + ("..." if len(chunk) > 200 else "")

            cards.append({
                "id": i,
                "question": question,
                "answer": answer,
                "source": chunk[:50] + "..."
            })

        return cards
