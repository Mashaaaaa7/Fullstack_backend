"""
QA Generator для PDF обработки
Использует fine-tuned T5 модель на SberQuAD датасете
С правильной подготовкой input и декодированием output
"""
import PyPDF2
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
import logging
from typing import List, Dict, Tuple
import re
import nltk
from nltk.tokenize import sent_tokenize

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем NLTK данные
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# Глобальные переменные для моделей
qg_model = None
qg_tokenizer = None


def load_qg_model():
    """Загружает fine-tuned модель генерации вопросов"""
    global qg_model, qg_tokenizer
    try:
        # Загружаем fine-tuned модель
        model_path = "./models/qg-finetuned"
        logger.info(f"📥 Загружаю fine-tuned модель из {model_path}...")

        qg_tokenizer = AutoTokenizer.from_pretrained(model_path)
        qg_model = AutoModelForSeq2SeqLM.from_pretrained(model_path)

        # Переводим на GPU если доступен
        device = "cuda" if torch.cuda.is_available() else "cpu"
        qg_model.to(device)
        qg_model.eval()

        logger.info(f"✓ Fine-tuned T5 модель загружена на {device}")
        return True

    except Exception as e:
        logger.error(f"✗ Ошибка загрузки fine-tuned модели: {e}")
        return False


def extract_text_from_pdf(pdf_path: str) -> List[str]:
    """Извлекает текст из PDF файла по страницам"""
    try:
        pages_text = []
        with open(pdf_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    extracted = page.extract_text()
                    if extracted and extracted.strip():
                        pages_text.append(extracted)
                except Exception as e:
                    logger.warning(f"Ошибка извлечения страницы {page_num}: {e}")
                    continue

        if not pages_text:
            logger.error("Не удалось извлечь текст из PDF")
            return []

        total_chars = sum(len(p) for p in pages_text)
        logger.info(f"✓ Извлечено {len(pages_text)} страниц, всего {total_chars} символов")
        return pages_text
    except Exception as e:
        logger.error(f"✗ Ошибка при чтении PDF: {e}")
        return []


def split_page_into_paragraphs(page_text: str) -> List[str]:
    """Разбивает текст страницы на абзацы"""
    paragraphs = re.split(r'\n\n+', page_text)

    valid_paragraphs = []
    for para in paragraphs:
        para = para.strip()
        if len(para) > 100:
            valid_paragraphs.append(para)

    return valid_paragraphs


def create_chunks_from_pages(pages_text: List[str]) -> List[str]:
    """Создаёт логические куски из страниц и абзацев"""
    chunks = []

    for page_num, page_text in enumerate(pages_text):
        paragraphs = split_page_into_paragraphs(page_text)

        if not paragraphs:
            continue

        i = 0
        while i < len(paragraphs):
            chunk = paragraphs[i]

            if i + 1 < len(paragraphs):
                combined = chunk + "\n\n" + paragraphs[i + 1]
                if len(combined) < 2000:
                    chunk = combined
                    i += 1

            if i + 1 < len(paragraphs):
                combined = chunk + "\n\n" + paragraphs[i + 1]
                if len(combined) < 2500:
                    chunk = combined
                    i += 1

            if chunk and len(chunk) > 100:
                chunks.append(chunk)

            i += 1

    logger.info(f"✓ Создано {len(chunks)} контекстных фрагментов")
    return chunks


def extract_sentences_as_candidates(text: str) -> List[Tuple[str, float]]:
    """
    Извлекает предложения как кандидаты для генерации вопросов
    """
    if not text or len(text.strip()) < 50:
        return []

    try:
        sentences = sent_tokenize(text)
    except:
        sentences = re.split(r'[.!?]', text)

    candidates = []

    for sentence in sentences:
        sentence = sentence.strip()

        # Пропускаем очень короткие предложения
        if len(sentence) < 20:
            continue

        # Пропускаем если это просто пунктуация
        if not re.search(r'[а-яА-Я]', sentence):
            continue

        # Все предложения имеют базовый приоритет
        score = 0.7

        # Длинные предложения более информативны
        if len(sentence) > 100:
            score = 0.85
        elif len(sentence) > 60:
            score = 0.8

        candidates.append((sentence, score))

    # Берём первые несколько предложений
    return candidates[:4]


def clean_generated_question(raw_text: str) -> str:
    """
    Тщательно очищает сгенерированный текст от артефактов
    """
    if not raw_text:
        return None

    text = str(raw_text).strip()

    # Убираем специальные токены T5
    text = re.sub(r'<extra_id_\d+>', '', text)
    text = re.sub(r'</s>|<s>|<pad>|<unk>|<mask>', '', text)

    # Убираем управляющие команды
    text = re.sub(r'generate\s+question:?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'question:?\s*', '', text, flags=re.IGNORECASE)

    # Убираем мусор из декодирования (повторяющиеся символы)
    text = re.sub(r'([а-яё])\1{2,}', r'\1', text)  # аааа -> а

    # Убираем множественные пробелы и пунктуацию
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'^[^\w\u0400-\u04FF]+', '', text)  # Мусор в начале
    text = re.sub(r'[^\w\u0400-\u04FF\.!?ё]+$', '', text)  # Мусор в конце

    # Если текст слишком короткий или пустой
    if not text or len(text) < 5:
        return None

    # Убеждаемся что заканчивается вопросительным знаком
    text = text.rstrip('.!,;:')
    if not text.endswith('?'):
        text = text + '?'

    logger.debug(f"Cleaned: {text}")
    return text


def generate_question_from_context(context: str) -> str:
    """
    Генерирует вопрос из контекста используя fine-tuned T5 модель
    Использует правильный формат input/output
    """

    if not qg_model or not qg_tokenizer:
        logger.warning("Модель не загружена")
        return None

    try:
        # Подготавливаем input - используем контекст как есть
        input_text = context[:500].strip()

        if not input_text:
            return None

        logger.debug(f"Input text: {input_text[:100]}...")

        # Токенизируем с правильными параметрами
        inputs = qg_tokenizer(
            input_text,
            max_length=512,
            truncation=True,
            padding="longest",
            return_tensors="pt"
        )

        # Генерируем на том же устройстве что и модель
        device = next(qg_model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            # Используем beam search для более хорошего качества
            output_ids = qg_model.generate(
                input_ids=inputs['input_ids'],
                attention_mask=inputs['attention_mask'],
                max_length=100,
                min_length=10,
                num_beams=5,
                temperature=0.7,
                do_sample=False,
                early_stopping=True,
                no_repeat_ngram_size=2,  # Избегаем повторений
                length_penalty=1.0
            )

        # Декодируем с skip_special_tokens=True
        raw_question = qg_tokenizer.decode(
            output_ids[0],
            skip_special_tokens=True
        ).strip()

        logger.debug(f"Raw output: {raw_question}")

        # Очищаем
        question = clean_generated_question(raw_question)

        if question and len(question) > 7:
            logger.debug(f"✓ Final question: {question}")
            return question

        logger.debug(f"❌ Question too short after cleaning")
        return None

    except Exception as e:
        logger.error(f"❌ Ошибка генерации вопроса: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_qa_from_text_neural(text: str, num_pairs: int = 2) -> List[Dict]:
    """
    Генерация QA пар используя fine-tuned neural модель
    """

    if not text or len(text.strip()) < 100:
        return []

    qa_pairs = []

    # Извлекаем предложения
    candidates = extract_sentences_as_candidates(text)

    if not candidates:
        logger.debug("Не найдены предложения для генерации")
        return []

    # Генерируем вопросы для каждого предложения
    for context, relevance in candidates[:num_pairs]:
        try:
            question = generate_question_from_context(context)

            # Проверяем валидность
            if (question and
                len(question) > 7 and
                question.endswith('?') and
                question.lower() != context.lower()[:len(question)]):

                qa_pairs.append({
                    "question": question,
                    "answer": context,
                    "confidence": round(float(relevance), 3)
                })
                logger.debug(f"✓ Valid pair created")
            else:
                if not question:
                    logger.debug(f"⚠️ No question generated")
                elif not question.endswith('?'):
                    logger.debug(f"⚠️ Question doesn't end with ?")
                else:
                    logger.debug(f"⚠️ Question matches answer")

        except Exception as e:
            logger.debug(f"Ошибка генерации QA: {e}")
            continue

    return qa_pairs


def process_pdf(pdf_path: str, max_cards: int = 10) -> List[Dict]:
    """Основной метод - обрабатывает PDF и генерирует карточки"""

    logger.info(f"🔄 Обработка PDF: {pdf_path}")

    pages_text = extract_text_from_pdf(pdf_path)
    if not pages_text:
        return []

    chunks = create_chunks_from_pages(pages_text)
    if not chunks:
        return []

    logger.info(f"📚 Всего фрагментов: {len(chunks)}")

    flashcards = []

    for i, chunk in enumerate(chunks):
        if len(flashcards) >= max_cards:
            logger.info(f"✓ Достаточно карточек ({len(flashcards)}/{max_cards})")
            break

        if (i + 1) % 5 == 0:
            logger.info(f"📝 Фрагмент {i + 1}/{len(chunks)}... (карточек: {len(flashcards)})")

        qa_pairs = generate_qa_from_text_neural(chunk, num_pairs=2)

        for qa in qa_pairs:
            if len(flashcards) < max_cards:
                flashcards.append({
                    "question": qa["question"],
                    "answer": qa["answer"],
                    "context": chunk[:300],
                    "confidence": qa["confidence"],
                    "source": pdf_path
                })

    logger.info(f"✅ Сгенерировано {len(flashcards)} карточек из {len(chunks)} фрагментов")
    return flashcards


class QAPair:
    """Класс QA генератора - основной интерфейс"""

    def __init__(self):
        """Инициализирует генератор и загружает fine-tuned модель"""
        logger.info("🔧 Инициализирую Neural QA генератор...")
        load_qg_model()

    def process_pdf(self, pdf_path: str, max_cards: int = 10) -> List[Dict]:
        """Обрабатывает PDF и возвращает список карточек"""
        return process_pdf(pdf_path, max_cards)

    def generate_qa(self, text: str) -> List[Dict]:
        """Генерирует QA пары из текста"""
        return generate_qa_from_text_neural(text)