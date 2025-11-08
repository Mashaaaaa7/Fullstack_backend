from transformers import pipeline
import pdfplumber
import re
import unicodedata
from typing import List, Dict
import torch
import random


class QAGenerator:
    def __init__(self):
        self.device = 0 if torch.cuda.is_available() else -1

        print("⏳ Загружаю модель для генерации контента...")

        # Используем одну модель для генерации вопросов и ответов
        self.generator = pipeline(
            "text2text-generation",
            model="google/flan-t5-small",
            device=self.device,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
        )

        print("✅ Модель загружена!")

    def clean_text(self, text: str) -> str:
        """Очищает текст от артефактов"""
        if not text:
            return ""

        # Удаляем невидимые символы
        text = ''.join(ch for ch in text if unicodedata.category(ch)[0] != 'C' or ch in '\n\t')

        # Удаляем множественные пробелы и странные символы
        text = re.sub(r'[>~<•»«„"\[\]]+', '', text)
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def extract_meaningful_text(self, file_path: str) -> List[Dict]:
        """Извлекает осмысленные фрагменты текста"""
        chunks = []
        try:
            with pdfplumber.open(file_path) as pdf:
                print(f"📄 PDF имеет {len(pdf.pages)} страниц")

                for i, page in enumerate(pdf.pages):
                    raw_text = page.extract_text()

                    if not raw_text:
                        continue

                    # Очищаем текст
                    text = self.clean_text(raw_text)

                    if len(text) < 100:
                        continue

                    # Разбиваем на абзацы и предложения
                    paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 50]

                    for para in paragraphs:
                        # Разбиваем на предложения
                        sentences = re.split(r'[.!?]+\s+', para)

                        for sent in sentences:
                            sent = self.clean_text(sent)
                            words = sent.split()

                            # Отбираем содержательные предложения
                            if (15 <= len(words) <= 40 and
                                    len(sent) > 30 and
                                    any(word.istitle() for word in words) and
                                    not any(tech in sent.lower() for tech in ['function', 'var ', 'const ', 'import'])):
                                chunks.append({
                                    "text": sent,
                                    "page": i + 1,
                                    "word_count": len(words)
                                })

            print(f"📊 Найдено {len(chunks)} содержательных фрагментов")
            return chunks

        except Exception as e:
            print(f"❌ Ошибка при извлечении текста: {e}")
            return []

    def generate_qa_pair(self, context: str) -> Dict:
        """Генерирует пару вопрос-ответ из контекста"""
        try:
            # Ограничиваем длину контекста для модели
            context_clean = self.clean_text(context[:500])

            if len(context_clean) < 30:
                return None

            # Промпт для генерации вопроса
            question_prompt = f"""
            Создай учебный вопрос на основе этого текста: {context_clean}
            Вопрос должен проверять понимание материала.
            """

            question_result = self.generator(
                question_prompt,
                max_new_tokens=50,
                num_beams=2,
                temperature=0.8
            )

            question = self.clean_text(question_result[0]['generated_text'])

            # Убеждаемся, что вопрос заканчивается знаком вопроса
            if not question.endswith('?'):
                question += '?'

            # Генерируем ответ на основе контекста
            answer_prompt = f"""
            На основе текста: {context_clean}
            Дай развернутый ответ на вопрос: {question}
            Ответ должен быть информативным и точным.
            """

            answer_result = self.generator(
                answer_prompt,
                max_new_tokens=100,
                num_beams=2,
                temperature=0.7
            )

            answer = self.clean_text(answer_result[0]['generated_text'])

            # Проверяем качество сгенерированной пары
            if (len(question) > 10 and len(answer) > 15 and
                    '?' in question and len(answer) > len(question)):

                return {
                    "question": question,
                    "answer": answer,
                    "context": context_clean[:200] + "..." if len(context_clean) > 200 else context_clean
                }
            else:
                return None

        except Exception as e:
            print(f"⚠️ Ошибка при генерации QA пары: {e}")
            return None

    def create_fallback_qa(self, context: str, idx: int) -> Dict:
        """Создает резервную QA пару если модель не справляется"""
        words = context.split()
        key_terms = [word for word in words if len(word) > 4 and word.isalpha()]

        if key_terms:
            term = random.choice(key_terms[:3])
            question = f"Что означает термин '{term}' в этом контексте?"
            answer = f"В данном контексте '{term}' относится к: {context[:150]}..."
        else:
            question = f"В чем основная идея этого утверждения?"
            answer = f"Основная идея: {context[:200]}..."

        return {
            "question": question,
            "answer": answer,
            "context": context[:150] + "..." if len(context) > 150 else context
        }

    def process_pdf(self, file_path: str, max_cards: int = 20) -> List[Dict]:
        print(f"\n🔄 Начинаю обработку {file_path}...")
        print(f"🎯 Цель: {max_cards} карточек")

        # Извлекаем текст
        chunks = self.extract_meaningful_text(file_path)

        if not chunks:
            print("❌ Не найдено подходящих текстовых фрагментов!")
            return []

        print(f"✅ Найдено {len(chunks)} содержательных фрагментов")

        # Сортируем по длине (предпочтение средним по длине фрагментам)
        chunks.sort(key=lambda x: abs(x['word_count'] - 25))  # Идеально 20-30 слов

        flashcards = []
        attempts = 0
        max_attempts = max_cards * 2  # Ограничиваем попытки

        for chunk in chunks:
            if len(flashcards) >= max_cards or attempts >= max_attempts:
                break

            attempts += 1

            # Пробуем сгенерировать QA пару с помощью модели
            qa_pair = self.generate_qa_pair(chunk['text'])

            if qa_pair:
                flashcard = {
                    "id": len(flashcards) + 1,
                    "question": qa_pair["question"],
                    "answer": qa_pair["answer"],
                    "context": qa_pair["context"],
                    "source": f"Page {chunk['page']}"
                }
                flashcards.append(flashcard)
                print(f"  ✅ [{len(flashcards)}] Q: {qa_pair['question'][:70]}...")
            else:
                # Используем резервный метод для каждого 3-го чанка
                if attempts % 3 == 0 and len(flashcards) < max_cards:
                    fallback_qa = self.create_fallback_qa(chunk['text'], len(flashcards) + 1)
                    flashcard = {
                        "id": len(flashcards) + 1,
                        "question": fallback_qa["question"],
                        "answer": fallback_qa["answer"],
                        "context": fallback_qa["context"],
                        "source": f"Page {chunk['page']}"
                    }
                    flashcards.append(flashcard)
                    print(f"  🔄 [{len(flashcards)}] Резервный: {fallback_qa['question'][:70]}...")

        # Если карточек все еще мало, добавляем простые
        if len(flashcards) < max_cards:
            remaining = max_cards - len(flashcards)
            print(f"🔄 Добавляю {remaining} простых карточек...")

            for i in range(remaining):
                if i < len(chunks):
                    chunk = chunks[i]
                    simple_qa = self.create_fallback_qa(chunk['text'], len(flashcards) + 1)
                    flashcard = {
                        "id": len(flashcards) + 1,
                        "question": simple_qa["question"],
                        "answer": simple_qa["answer"],
                        "context": simple_qa["context"],
                        "source": f"Page {chunk['page']}"
                    }
                    flashcards.append(flashcard)

        print(f"✅ Создано {len(flashcards)} карточек из {attempts} попыток")
        return flashcards