from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
import pdfplumber
import re
from typing import List, Dict

class QAGenerator:
    def __init__(self, model_name: str = "google/flan-t5-large"):
        print(f"Инициализация модели {model_name}...", flush=True)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        if self.device == "cuda":
            self.model.to("cuda")
        print(f"Модель загружена на {self.device}", flush=True)

    def extract_text_from_pdf(self, file_path: str) -> List[str]:
        """Извлекает параграфы из PDF"""
        paragraphs = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    paras = text.split("\n\n")
                    for p in paras:
                        cleaned = re.sub(r'\s+', ' ', p).strip()
                        if len(cleaned) > 50:  # минимальная длина параграфа
                            paragraphs.append(cleaned)
        return paragraphs

    def generate_question(self, text: str) -> str:
        """Генерирует вопрос по тексту"""
        prompt = f"Сделай вопрос по следующему тексту: {text}"
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        if self.device == "cuda":
            inputs = {k:v.to("cuda") for k,v in inputs.items()}
        outputs = self.model.generate(**inputs, max_length=128)
        question = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return question

    def process_pdf(self, file_path: str, max_cards: int = 10) -> List[Dict[str, str]]:
        """Основная функция для генерации flashcards"""
        paragraphs = self.extract_text_from_pdf(file_path)
        flashcards = []
        used_questions = set()

        for para in paragraphs:
            if len(flashcards) >= max_cards:
                break
            sentences = re.split(r'(?<=[.!?])\s+', para)
            for sentence in sentences:
                if len(flashcards) >= max_cards:
                    break
                if len(sentence) < 20:  # слишком короткие предложения пропускаем
                    continue
                try:
                    question = self.generate_question(sentence)
                    if question in used_questions:
                        continue
                    used_questions.add(question)
                    flashcards.append({
                        "question": question,
                        "answer": sentence.strip(),
                        "context": para[:100]
                    })
                except Exception as e:
                    print(f"Ошибка генерации: {e}", flush=True)
                    continue

        return flashcards