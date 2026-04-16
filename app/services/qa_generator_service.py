from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
import fitz
import re
import torch


class QAGeneratorService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._initialize()
            cls._instance = instance
        return cls._instance

    def _initialize(self):
        print("🔧 Инициализирую QAGenerator...")
        try:
            self.qg_model_name = "iarfmoose/t5-base-question-generator"
            self.qg_tokenizer = AutoTokenizer.from_pretrained(self.qg_model_name)
            self.qg_model = AutoModelForSeq2SeqLM.from_pretrained(
                self.qg_model_name,
                torch_dtype=torch.float32
            ).to("cpu")
            self.qa_pipeline = pipeline(
                "question-answering",
                model="distilbert-base-uncased-distilled-squad"
            )
            print("✅ QAGenerator готов")
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
        if current.strip():
            chunks.append(current.strip())
        return chunks

    def generate_question(self, context: str):
        prompt = "generate question: " + context
        inputs = self.qg_tokenizer(
            prompt, return_tensors="pt", truncation=True
        ).to(self.qg_model.device)
        outputs = self.qg_model.generate(**inputs, max_new_tokens=64, do_sample=False)
        return self.qg_tokenizer.decode(outputs[0], skip_special_tokens=True).strip()

    def extract_answer(self, question: str, context: str):
        result = self.qa_pipeline(question=question, context=context)
        answer = result["answer"].strip()
        return answer if answer else "NONE"

    def process_pdf(self, pdf_path: str, max_cards: int):
        text = self.extract_text(pdf_path)
        chunks = self.split_into_chunks(text)
        cards = []

        for i, chunk in enumerate(chunks):
            if len(cards) >= max_cards:
                break
            print(f"Обработка чанка {i + 1}/{len(chunks)}")
            try:
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
                    "source": self.qg_model_name
                })
            except Exception as e:
                print(f"⚠️ Пропускаю чанк {i + 1}: {e}")
                continue

        return cards