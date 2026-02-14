from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
import fitz
import re

class QAGenerator:
    def __init__(self):
        # Модель для генерации вопросов
        self.qg_model_name = "iarfmoose/t5-base-question-generator"
        self.qg_tokenizer = AutoTokenizer.from_pretrained(self.qg_model_name)
        self.qg_model = AutoModelForSeq2SeqLM.from_pretrained(
            self.qg_model_name,
            device_map="auto"
        )

        # Модель для извлечения ответа (легкая, быстрый inference)
        self.qa_pipeline = pipeline("question-answering", model="distilbert-base-uncased-distilled-squad")

    def extract_text(self, pdf_path: str) -> str:
        """Чтение текста из PDF"""
        doc = fitz.open(pdf_path)
        return "\n".join(page.get_text() for page in doc)

    def split_into_chunks(self, text: str, max_len=900, min_len=300):
        """Разбиваем текст на куски для генерации вопросов"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks, current = [], ""
        for s in sentences:
            if len(current) + len(s) < max_len:
                current += " " + s
            else:
                if len(current) >= min_len:
                    chunks.append(current.strip())
                current = s
        if len(current) >= min_len:
            chunks.append(current.strip())
        return chunks

    def generate_question(self, context: str):
        """Генерируем вопрос из текста"""
        prompt = "generate question: " + context
        inputs = self.qg_tokenizer(prompt, return_tensors="pt", truncation=True).to(self.qg_model.device)
        outputs = self.qg_model.generate(**inputs, max_new_tokens=64, do_sample=False)
        question = self.qg_tokenizer.decode(outputs[0], skip_special_tokens=True)
        return question.strip()

    def extract_answer(self, question: str, context: str):
        """Извлекаем короткий ответ из текста"""
        result = self.qa_pipeline(question=question, context=context)
        return result["answer"].strip() if result["answer"] else "NONE"

    def process_pdf(self, pdf_path: str, max_cards: int):
        """Основной метод: генерируем карточки по PDF"""
        text = self.extract_text(pdf_path)
        chunks = self.split_into_chunks(text)
        cards = []

        for chunk in chunks:
            if len(cards) >= max_cards:
                break

            # Генерируем вопрос
            question = self.generate_question(chunk)
            if len(question) < 5:
                continue

            # Получаем ответ
            answer = self.extract_answer(question, chunk)
            if answer.upper() == "NONE":
                continue

            cards.append({
                "question": question,
                "answer": answer,
                "context": chunk[:200],
                "source": "iarfmoose/t5-base-question-generator"
            })

        return cards