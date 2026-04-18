from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, AutoModelForQuestionAnswering
import fitz
import re
import torch


class QAGeneratorService:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _initialize(self):
        if self._initialized:
            return
        print("🔧 Инициализирую QAGenerator...")
        try:
            # T5 — генерация вопросов
            self.qg_model_name = "iarfmoose/t5-base-question-generator"
            self.qg_tokenizer = AutoTokenizer.from_pretrained(self.qg_model_name)
            self.qg_model = AutoModelForSeq2SeqLM.from_pretrained(
                self.qg_model_name,
                torch_dtype=torch.float32
            ).to("cpu")

            # ✅ DistilBERT — поиск ответов (без pipeline, напрямую)
            qa_model_name = "distilbert-base-uncased-distilled-squad"
            self.qa_tokenizer = AutoTokenizer.from_pretrained(qa_model_name)
            self.qa_model = AutoModelForQuestionAnswering.from_pretrained(qa_model_name)
            self.qa_model.eval()

            self._initialized = True
            print("✅ QAGenerator инициализирован")
        except Exception as e:
            print(f"❌ Ошибка инициализации QAGenerator: {e}")
            raise

    def extract_text(self, pdf_path: str) -> str:
        doc = fitz.open(pdf_path)
        return "\n".join(page.get_text() for page in doc)

    def split_into_chunks(self, text: str, max_len=900, min_len=300):
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

    def generate_question(self, context: str) -> str:
        prompt = "generate question: " + context
        inputs = self.qg_tokenizer(
            prompt, return_tensors="pt", truncation=True
        ).to(self.qg_model.device)
        outputs = self.qg_model.generate(**inputs, max_new_tokens=64, do_sample=False)
        return self.qg_tokenizer.decode(outputs[0], skip_special_tokens=True).strip()

    def extract_answer(self, question: str, context: str) -> str:
        # ✅ Прямой вызов вместо pipeline()
        inputs = self.qa_tokenizer(
            question, context,
            return_tensors="pt",
            truncation=True,
            max_length=512
        )
        with torch.no_grad():
            outputs = self.qa_model(**inputs)
        start = outputs.start_logits.argmax()
        end = outputs.end_logits.argmax() + 1
        tokens = inputs["input_ids"][0][start:end]
        answer = self.qa_tokenizer.convert_tokens_to_string(
            self.qa_tokenizer.convert_ids_to_tokens(tokens)
        ).strip()
        return answer if answer else "NONE"

    def process_pdf(self, pdf_path: str, max_cards: int):
        if not self._initialized:
            self._initialize()

        text = self.extract_text(pdf_path)
        chunks = self.split_into_chunks(text)
        cards = []

        for i, chunk in enumerate(chunks):
            if len(cards) >= max_cards:
                break
            print(f"Обработка чанка {i + 1}/{len(chunks)}")

            question = self.generate_question(chunk)
            if len(question) < 5:
                continue

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