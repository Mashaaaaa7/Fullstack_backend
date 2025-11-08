from transformers import pipeline
import pdfplumber
import re
from typing import List, Dict
import torch

class QAGenerator:
    def __init__(self):
        self.device = 0 if torch.cuda.is_available() else -1
        self.qg_pipeline = pipeline(
            "text2text-generation",
            model="valhalla/t5-base-qg-hl",
            device=self.device
        )
        self.qa_pipeline = pipeline(
            "question-answering",
            model="deepset/roberta-base-squad2",
            device=self.device
        )

    def extract_text_chunks(self, file_path: str) -> List[Dict]:
        chunks = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        sentences = re.split(r'[.!?]\s+', text)
                        for sent in sentences:
                            sent = sent.strip()
                            if len(sent) > 20:
                                chunks.append({"text": sent, "page": i+1})
        except Exception:
            return []
        return chunks

    def generate_question(self, context: str, answer_highlight: str) -> str:
        input_text = f"generate question: {context[:300]} \\n highlight: {answer_highlight[:50]}"
        result = self.qg_pipeline(input_text, max_length=64, num_beams=4)
        question = result[0]['generated_text'].strip()
        if not question.endswith("?"):
            question += "?"
        return question

    def answer_question(self, context: str, question: str) -> str:
        res = self.qa_pipeline(question=question, context=context[:1000])
        return res['answer']

    def process_pdf(self, file_path: str, max_cards: int = 10) -> List[Dict]:
        chunks = self.extract_text_chunks(file_path)
        if not chunks:
            return []

        step = max(1, len(chunks) // max_cards)
        selected_chunks = chunks[::step][:max_cards]

        flashcards = []
        for idx, chunk in enumerate(selected_chunks, 1):
            context = chunk['text']
            keywords = context.split()[:5]
            question = self.generate_question(context, keywords[0] if keywords else context[:20])
            answer = self.answer_question(context, question)
            flashcards.append({
                "id": idx,
                "question": question,
                "answer": answer,
                "context": context,
                "source": f"Page {chunk['page']}"
            })
        return flashcards
