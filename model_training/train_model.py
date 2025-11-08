# train_model.py (ИСПРАВЛЕННАЯ ВЕРСИЯ)

from transformers import (
    T5ForConditionalGeneration,
    T5Tokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorForSeq2Seq
)
from prepare_dataset import prepare_dataset_for_t5
import torch

# Проверка GPU
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Используется устройство: {device}")

# 1. Загрузка базовой модели
print("Загрузка модели...")
model_name = "cointegrated/rut5-base-multitask"  # Русская T5
tokenizer = T5Tokenizer.from_pretrained(model_name)
model = T5ForConditionalGeneration.from_pretrained(model_name)

print(f"✅ Модель загружена: {model_name}")

# 2. Загрузка датасета
print("Подготовка датасета...")
dataset = prepare_dataset_for_t5()


# 3. Токенизация
def tokenize_function(examples):
    """Преобразует текст в токены"""
    model_inputs = tokenizer(
        examples['input_text'],
        max_length=512,
        truncation=True,
        padding='max_length'
    )

    # Токенизация целевых текстов
    labels = tokenizer(
        examples['target_text'],
        max_length=128,
        truncation=True,
        padding='max_length'
    )

    model_inputs['labels'] = labels['input_ids']
    return model_inputs


print("Токенизация...")
tokenized_dataset = dataset.map(tokenize_function, batched=True)

# 4. Data Collator
data_collator = DataCollatorForSeq2Seq(
    tokenizer=tokenizer,
    model=model
)

# 5. Настройки обучения (✅ ИСПРАВЛЕНО)
training_args = TrainingArguments(
    output_dir="./fine_tuned_model",  # Где сохранить модель
    eval_strategy="epoch",  # ✅ ИСПРАВЛЕНО: было evaluation_strategy
    learning_rate=3e-4,  # Скорость обучения
    per_device_train_batch_size=4,  # Размер батча
    per_device_eval_batch_size=4,
    num_train_epochs=3,  # Количество эпох
    weight_decay=0.01,  # Регуляризация
    save_total_limit=2,  # Сохранять только 2 последних чекпоинта
    logging_dir="./logs",
    logging_steps=50,
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="eval_loss",
    fp16=False,  # ✅ ИСПРАВЛЕНО: False для CPU
    report_to="none"  # Отключить wandb/tensorboard
)

# 6. Инициализация Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset["train"],
    eval_dataset=tokenized_dataset["test"],
    tokenizer=tokenizer,
    data_collator=data_collator
)

# 7. ОБУЧЕНИЕ
print("\n🚀 Начинаем обучение...")
trainer.train()

# 8. Оценка модели
print("\n📊 Оценка модели...")
eval_results = trainer.evaluate()
print(f"Результаты: {eval_results}")

# 9. Сохранение модели
print("\n💾 Сохранение модели...")
model.save_pretrained("./fine_tuned_model/best_model")
tokenizer.save_pretrained("./fine_tuned_model/best_model")

print("✅ Обучение завершено! Модель сохранена в ./fine_tuned_model/best_model")
