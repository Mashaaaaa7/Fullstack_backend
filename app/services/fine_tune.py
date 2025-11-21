"""
Fine-tuning скрипт для Question Generation модели на SberQuAD датасете
Минимальные зависимости - совместимо со старыми версиями transformers
"""

from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, Trainer, TrainingArguments, DataCollatorForSeq2Seq
import torch

'''
Пример: размер батча 4 означает, что 4 примера используются для вычисления градиента 
и обновления весов модели перед обработкой следующей партии из 4 примеров. 
'''
# Параметры
MODEL_NAME = "google/mt5-small"
DATASET_NAME = "kuznetsoffandrey/sberquad"
OUTPUT_DIR = "./models/qg-finetuned"
BATCH_SIZE = 4
EPOCHS = 1
MAX_INPUT_LENGTH = 512  # Длинные контексты
MAX_TARGET_LENGTH = 100  # Длинные вопросы


print("📥 Загружаю SberQuAD датасет...")
dataset = load_dataset(DATASET_NAME)

print(f"Размер датасета: {len(dataset['train'])} примеров")

# Показываем пример
example = dataset['train'][0]
print(f"\nПример из датасета:")
print(f"Context: {example['context'][:200]}...")
print(f"Question: {example['question']}")
print(f"Answer: {example['answers']['text'][0]}")

# Загружаем модель и токенайзер
print("\n🔧 Загружаю модель и токенайзер...")
try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
except Exception as e:
    print(f"Ошибка загрузки {MODEL_NAME}: {e}")
    print("Попытка загрузить fallback модель...")
    MODEL_NAME = "t5-small"
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Используем: {device}")
print(f"Модель: {MODEL_NAME}")

# Подготовка датасета
def preprocess_function(examples):
    """Преобразуем SberQuAD в формат для Question Generation"""

    inputs = []
    targets = []

    for i in range(len(examples['context'])):
        context = examples['context'][i]
        question = examples['question'][i]

        input_text = context

        inputs.append(input_text)
        targets.append(question)

    # Tokenize
    model_inputs = tokenizer(
        inputs,
        max_length=MAX_INPUT_LENGTH,
        truncation=True,
        padding="max_length"
    )

    labels = tokenizer(
        targets,
        max_length=MAX_TARGET_LENGTH,
        truncation=True,
        padding="max_length"
    )

    model_inputs["labels"] = labels["input_ids"]

    return model_inputs

print("\n⚙️ Обработка датасета...")
train_size = min(5000, len(dataset['train']))  # Еще меньше для старой версии
print(f"Используем {train_size} примеров для обучения")

train_dataset = dataset['train'].select(range(train_size))
val_size = min(500, len(dataset['validation']))
eval_dataset = dataset['validation'].select(range(val_size))

processed_train = train_dataset.map(
    preprocess_function,
    batched=True,
    batch_size=500,
    remove_columns=train_dataset.column_names,
    desc="Processing train"
)

processed_eval = eval_dataset.map(
    preprocess_function,
    batched=True,
    batch_size=500,
    remove_columns=eval_dataset.column_names,
    desc="Processing eval"
)

print(f"Train: {len(processed_train)}, Eval: {len(processed_eval)}")

# Training arguments - совместимо со ОЧЕНЬ старыми версиями
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    per_device_train_batch_size=BATCH_SIZE,
    per_device_eval_batch_size=BATCH_SIZE,
    num_train_epochs=EPOCHS,
    weight_decay=0.01,
    save_total_limit=1,
    logging_steps=100,
    save_steps=500,
    warmup_steps=100,
    report_to="none"
)

# Data collator
data_collator = DataCollatorForSeq2Seq(tokenizer, model=model)

# Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=processed_train,
    eval_dataset=processed_eval,
    data_collator=data_collator,
)

print("\n🚀 Начинаю fine-tuning...")
print(f"📊 Батч: {BATCH_SIZE}, Эпохи: {EPOCHS}, Примеров: {len(processed_train)}")
print(f"💾 Модель будет сохранена в: {OUTPUT_DIR}")

trainer.train()

print(f"\n✅ Готово! Модель сохранена в {OUTPUT_DIR}")

# Сохраняем финальную версию
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print("✓ Модель и токенайзер сохранены")
print("\n📝 qa_generator.py автоматически использует обученную модель")