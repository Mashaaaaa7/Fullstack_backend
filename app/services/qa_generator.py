import re
import unicodedata
from typing import List, Dict
from transformers import pipeline
import pdfplumber
import torch

class QAGenerator:
    def __init__(self, use_gpt: bool = False, model_name: str = "cointegrated/rut5-base-multitask"):
        # Device
        self.device = 0 if torch.cuda.is_available() else -1
        self.use_gpt = use_gpt
        print("⏳ Загружаю русскую модель...")
        self.generator = pipeline(
            "text2text-generation",
            model="cointegrated/rut5-base-multitask",
            device=self.device,
            torch_dtype=torch.float32
        )
        print("✅ Модель загружена!")

    def clean_text(self, text: str) -> str:
        """Очищает текст от артефактов"""
        if not text:
            return ""
        text = ''.join(ch for ch in text if unicodedata.category(ch)[0] != 'C' or ch in '\n\t')
        text = re.sub(r'[>~<•»«„"\[\]{}()_\-–—]+', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def extract_meaningful_text(self, file_path: str) -> List[Dict]:
        """Извлекает осмысленные фрагменты"""
        chunks = []
        try:
            with pdfplumber.open(file_path) as pdf:
                print(f"📄 PDF имеет {len(pdf.pages)} страниц")

                for i, page in enumerate(pdf.pages):
                    raw_text = page.extract_text()
                    if not raw_text:
                        continue

                    text = self.clean_text(raw_text)
                    if len(text) < 100:
                        continue

                    text = re.sub(r'^\d{2}\.\d{2}\.\d{4}.*?Colab\s*', '', text)
                    text = re.sub(r'https?://[^\s]+', '', text)
                    text = re.sub(r'\d{4}.*?ipynb.*?Colab', '', text, flags=re.IGNORECASE)

                    paragraphs = [p.strip() for p in text.split('\n') if len(p.strip()) > 50]

                    for para in paragraphs:
                        chunks_from_para = self._split_into_chunks(para)
                        chunks.extend(chunks_from_para)

            chunks = [c for c in chunks if not any(
                bad in c['text'].lower() for bad in ['ipynb', 'colab', 'http', '©', '®']
            )]

            print(f"📊 Найдено {len(chunks)} содержательных фрагментов")
            return chunks
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return []

    def _split_into_chunks(self, text: str) -> List[Dict]:
        """Разбивает текст на смысловые куски"""
        chunks = []
        sentences = re.split(r'[.!?]+\s+', text)

        combined = []
        current = ""

        for sent in sentences:
            sent = sent.strip()
            if not sent or len(sent) < 5:
                continue

            current += sent + ". "

            if len(current.split()) >= 12:
                combined.append(current.strip())
                current = ""

        if current.strip():
            combined.append(current.strip())

        for chunk_text in combined:
            if len(chunk_text) > 60:
                chunks.append({
                    "text": chunk_text,
                    "page": 0,
                    "word_count": len(chunk_text.split())
                })

        return chunks

    def _clean_question(self, text: str) -> str:
        """Очищает вопрос от мусора"""
        # Удаляем промпты в начале
        text = re.sub(r'^напишите вопрос.*?:\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^вопрос.*?:\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^на основе.*?:\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^создайте.*?:\s*', '', text, flags=re.IGNORECASE)

        # Убираем мусор в конце
        text = text.rstrip('.,;:')

        # Капитализируем
        if text:
            text = text[0].upper() + text[1:].lower()

        # Добавляем ?
        if text and not text.endswith('?'):
            text += '?'

        return text.strip()

    def _generate_question_rut5(self, answer: str) -> str:
        """Генерирует вопрос через RuT5"""
        try:
            text_sample = answer[:250]

            # ЛУЧШИЙ ПРОМПТ
            prompt = f"Создайте вопрос к тексту: {text_sample}"

            result = self.generator(
                prompt,
                max_new_tokens=40,
                num_beams=3,
                temperature=0.6
            )

            question = self.clean_text(result[0]['generated_text']).strip()
            question = self._clean_question(question)

            # Проверяем качество
            if (15 < len(question) < 120 and '?' in question and
                    not question.lower().startswith('напишите') and
                    not question.lower().startswith('создайте')):
                return question

            return None
        except Exception as e:
            print(f"⚠️ RuT5 ошибка: {e}")
            return None

    def _generate_universal_question(self, answer: str) -> str:
        """Fallback: шаблоны вопросов"""
        words = answer.split()
        answer_lower = answer.lower()

        bad_words = {'это', 'для', 'при', 'как', 'что', 'в', 'по', 'на', 'с', 'и', 'или', 'то',
                     'был', 'была', 'были', 'быть', 'являются', 'является', 'есть', 'имели',
                     'имеют', 'находится', 'находились', 'важный', 'важная', 'главный', 'новый'}

        idx = 0
        while idx < len(words) and words[idx].lower() in bad_words:
            idx += 1

        remaining_words = words[idx:]

        for w in remaining_words[:12]:
            w_lower = w.lower().rstrip(',:;.')
            if (len(w_lower) > 4 and w[0].isupper() and w_lower not in bad_words and
                    not w_lower.endswith('ом') and not w_lower.endswith('ый') and
                    not w_lower.endswith('ой')):
                key_phrase = w_lower
                break
        else:
            key_phrase = "процесс"

        if any(word in answer_lower for word in ['оказала', 'привел', 'вызва']):
            return f"Какое воздействие имел {key_phrase}?"
        elif any(word in answer_lower for word in ['развив', 'эволюц', 'преобразов']):
            return f"Как происходило развитие {key_phrase}?"
        elif any(word in answer_lower for word in ['привела', 'послужила', 'способствова']):
            return f"Какие факторы способствовали {key_phrase}?"
        elif any(word in answer_lower for word in ['играла', 'выполня', 'служила']):
            return f"Какую роль выполнял {key_phrase}?"
        elif any(word in answer_lower for word in ['содержит', 'включает']):
            return f"Из чего состоит {key_phrase}?"
        else:
            return f"Объясните, что такое {key_phrase}?"

    def _is_corrupted_text(self, text: str) -> bool:
        """Проверяет, не повреждён ли текст"""
        # Проверяем на мусор
        if any(pattern in text for pattern in [
            'znp', 'Zogitp', 'modelnp', 'znà', 'sà', 'ру=о', 'nоrистической'
        ]):
            return True

        # Проверяем на слишком много символов = или ?
        if text.count('=') > 2 or text.count('?') > 1:
            return True

        # Проверяем на кириллицу + латиницу в одном слове
        if re.search(r'[а-яА-Я][a-zA-Z]|[a-zA-Z][а-яА-Я]', text):
            return True

        return False

    def generate_qa_pair(self, context: str) -> Dict:
        """Генерирует QA с фильтрацией мусора"""
        try:
            context_clean = self.clean_text(context[:700])
            context_clean = re.sub(r'\s+', ' ', context_clean).strip()

            if len(context_clean) < 120:
                return None

            # Проверяем на повреждённый текст ИЗ PDF
            if self._is_corrupted_text(context_clean):
                return None

            if any(word in context_clean.lower() for word in
                   ['код', 'import', 'def ', 'print(', 'function', 'class ']):
                return None

            sentences = [s.strip() for s in re.split(r'[.!?]+', context_clean)]
            candidate_sents = [s for s in sentences if len(s.split()) >= 12 and len(s) > 100]

            if not candidate_sents:
                return None

            answer = candidate_sents[0]

            question = self._generate_question_rut5(answer)

            # Fallback
            if not question:
                question = self._generate_universal_question(answer)

            if not question:
                return None

            answer = re.sub(r'\s+', ' ', answer).strip()
            question = re.sub(r'\s+', ' ', question).strip()

            if len(question) > 15 and len(answer) > 100:
                return {
                    "question": question,
                    "answer": answer,
                    "context": context_clean[:150]
                }

            return None

        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
            return None

    def process_pdf(self, file_path: str, max_cards: int = 10) -> List[Dict]:
        """Обрабатывает PDF и генерирует карточки"""
        print(f"\n🔄 Начинаю обработку {file_path}...")
        print(f"🎯 Цель: {max_cards} карточек")

        chunks = self.extract_meaningful_text(file_path)

        if not chunks:
            print("❌ Не найдено подходящих текстовых фрагментов!")
            return []

        print(f"✅ Найдено {len(chunks)} содержательных фрагментов")

        chunks.sort(key=lambda x: abs(x['word_count'] - 25))
        flashcards = []

        for chunk in chunks[:max_cards * 2]:
            if len(flashcards) >= max_cards:
                break

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
                print(f"  ✅ [{len(flashcards)}] {qa_pair['question'][:60]}...")

        print(f"✅ Создано {len(flashcards)} карточек")
        return flashcards
