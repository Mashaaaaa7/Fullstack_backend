from transformers import pipeline
import pdfplumber
import re
from typing import List, Dict
import torch


class QAGenerator:
    def __init__(self):
        self.device = 0 if torch.cuda.is_available() else -1

        print("⏳ Загружаю модель для генерации вопросов...")

        self.qg_pipeline = pipeline(
            "text2text-generation",
            model="google/flan-t5-small",
            device=self.device
        )

        print("⏳ Загружаю модель для поиска ответов...")
        self.qa_pipeline = pipeline(
            "question-answering",
            model="deepset/roberta-base-squad2",
            device=self.device
        )

        print("✅ Обе модели загружены!")

    def extract_text_chunks(self, file_path: str) -> List[Dict]:
        chunks = []
        try:
            with pdfplumber.open(file_path) as pdf:
                print(f"📄 PDF имеет {len(pdf.pages)} страниц")

                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()

                    if not text or not text.strip():
                        print(f"⚠️ Страница {i + 1}: текст не найден (возможно сканированное изображение)")
                        continue

                    # Очищаем текст от лишних символов
                    text = re.sub(r'\s+', ' ', text).strip()

                    if len(text) < 50:
                        print(f"⚠️ Страница {i + 1}: текст слишком короткий ({len(text)} символов)")
                        continue

                    # Разбиваем на предложения
                    sentences = re.split(r'[.!?]+\s+', text)

                    for sent in sentences:
                        sent = sent.strip()
                        # Требуем минимум 20 символов и максимум 300
                        if 20 <= len(sent) <= 400:
                            chunks.append({
                                "text": sent,
                                "page": i + 1
                            })

                    print(f"✅ Страница {i + 1}: извлечено {len([c for c in chunks if c['page'] == i + 1])} предложений")

                print(f"📊 Всего чанков: {len(chunks)}")
        except Exception as e:
            print(f"❌ Ошибка при извлечении текста: {e}")
            return []

        return chunks

    def generate_question(self, context: str, answer_highlight: str) -> str:
        try:
            # Ограничиваем длину для модели
            context_clean = context[:200].replace("\n", " ").strip()
            answer_clean = answer_highlight[:30].replace("\n", " ").strip()

            if not context_clean or not answer_clean:
                return f"Вопрос о {answer_clean[:20]}"

            input_text = f"generate question: {context_clean} answer: {answer_clean}"

            result = self.qg_pipeline(
                input_text,
                max_new_tokens=32,
                num_beams=2
            )
            question = result[0]['generated_text'].strip()

            question = question.replace("generate question:", "").strip()

            if not question or len(question) < 5:
                question = f"Что значит '{answer_clean}'?"

            if not question.endswith("?"):
                question += "?"

            return question
        except Exception as e:
            print(f"⚠️ Ошибка при генерации вопроса: {e}")
            return f"Вопрос о '{answer_clean}'?"

    def answer_question(self, context: str, question: str) -> str:
        if not context or len(context) < 30:
            return context[:100]

        try:
            res = self.qa_pipeline(question=question, context=context[:800])
            answer = res['answer'].strip()
            return answer if answer and len(answer) > 2 else context[:100]
        except Exception as e:
            print(f"⚠️ Ошибка при поиске ответа: {e}")
            return context[:100]

    def process_pdf(self, file_path: str, max_cards: int = 10) -> List[Dict]:
        print(f"\n🔄 Начинаю обработку {file_path}...")

        chunks = self.extract_text_chunks(file_path)

        if not chunks:
            print("❌ Чанки не найдены! PDF может быть отсканированным изображением.")
            return []

        print(f"✅ Найдено {len(chunks)} чанков")

        step = max(1, len(chunks) // max_cards)
        selected_chunks = chunks[::step][:max_cards]

        print(f"📌 Выбрано {len(selected_chunks)} чанков для обработки")

        flashcards = []
        for idx, chunk in enumerate(selected_chunks, 1):
            context = chunk['text']

            # Извлекаем слова как потенциальный ответ
            words = re.findall(r'\b[А-Яа-яA-Za-z]{3,}\b', context)
            answer_highlight = words[0] if words else context[:30]

            question = self.generate_question(context, answer_highlight)
            answer = self.answer_question(context, question)

            flashcard = {
                "id": idx,
                "question": question,
                "answer": answer,
                "context": context,
                "source": f"Page {chunk['page']}"
            }
            flashcards.append(flashcard)

            print(f"  [{idx}] Q: {question[:50]}... A: {answer[:50]}...")

        print(f"✅ Создано {len(flashcards)} карточек")
        return flashcards
