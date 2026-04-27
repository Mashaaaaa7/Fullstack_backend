# app/services/qa_generator_service.py
class QAGeneratorService:
    def __init__(self):
        self.generator = None
        self._init_error = None

    def _ensure_model(self):
        if self.generator is not None:
            return
        if self._init_error is not None:
            raise RuntimeError(f"QA model unavailable: {self._init_error}")

        try:
            import torch  # noqa
            from transformers import pipeline
            self.generator = pipeline(
                "text2text-generation",
                model="iarfmoose/t5-base-question-generator"
            )
            print("✅ QAGenerator инициализирован")
        except Exception as e:
            self._init_error = str(e)
            raise RuntimeError(f"QA model init failed: {e}")

    def generate(self, text: str):
        self._ensure_model()
        return self.generator(text)