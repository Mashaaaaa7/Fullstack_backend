# test_model.py

from transformers import T5ForConditionalGeneration, T5Tokenizer

# Загрузка обученной модели
model = T5ForConditionalGeneration.from_pretrained("./fine_tuned_model/best_model")
tokenizer = T5Tokenizer.from_pretrained("./fine_tuned_model/best_model")


def generate_question(context: str) -> str:
    """Генерирует вопрос из контекста"""
    input_text = f"generate question: {context}"

    inputs = tokenizer(
        input_text,
        return_tensors="pt",
        max_length=512,
        truncation=True
    )

    outputs = model.generate(
        **inputs,
        max_length=64,
        num_beams=4,
        early_stopping=True
    )

    question = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return question


# Тестирование
test_context = "React - это JavaScript библиотека для создания пользовательских интерфейсов, разработанная Facebook."
question = generate_question(test_context)
print(f"Контекст: {test_context}")
print(f"Вопрос: {question}")
