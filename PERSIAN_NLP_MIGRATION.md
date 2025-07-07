# 🔧 راهنمای Migration از hazm به ابزارهای مدرن NLP فارسی

## 📋 دلیل تغییر

- **hazm** نیاز به `nltk==3.3` دارد که دارای آسیب‌پذیری امنیتی است
- **crawl4ai** نیاز به `nltk>=3.9.1` دارد
- استفاده از ابزارهای مدرن‌تر و امن‌تر

## 🔄 جایگزین‌های پیشنهادی

### 1. **spaCy** (اصلی)
```python
# قبل (hazm)
from hazm import Normalizer, word_tokenize, sent_tokenize

# بعد (spaCy)
import spacy
nlp = spacy.load("xx_ent_wiki_sm")  # Multilingual model
```

### 2. **parsivar** (برای توکنایزیشن فارسی)
```python
# parsivar برای پردازش متن فارسی
from parsivar import Normalizer, Tokenizer

normalizer = Normalizer()
tokenizer = Tokenizer()
```

### 3. **persian-tools** (ابزارهای کمکی)
```python
# برای کارهای عمومی فارسی
from persian_tools import digits, phone_number
```

## 🛠️ نحوه پیاده‌سازی

### کد قدیمی (hazm):
```python
from hazm import Normalizer, word_tokenize, sent_tokenize

normalizer = Normalizer()
text = normalizer.normalize("متن فارسی")
words = word_tokenize(text)
sentences = sent_tokenize(text)
```

### کد جدید (spaCy + parsivar):
```python
import spacy
from parsivar import Normalizer, Tokenizer

# spaCy برای NLP عمومی
nlp = spacy.load("xx_ent_wiki_sm")

# parsivar برای پردازش فارسی
normalizer = Normalizer()
tokenizer = Tokenizer()

# پردازش متن
text = normalizer.normalize("متن فارسی")
words = tokenizer.tokenize_words(text)
sentences = tokenizer.tokenize_sentences(text)

# تحلیل با spaCy
doc = nlp(text)
for token in doc:
    print(token.text, token.pos_, token.lemma_)
```

## 📦 نصب مدل spaCy فارسی

```bash
# نصب مدل چندزبانه
python -m spacy download xx_ent_wiki_sm

# یا استفاده از مدل‌های اختصاصی فارسی (در صورت وجود)
python -m spacy download fa_core_news_sm
```

## 🔧 فایل‌های نیاز به تغییر

1. **data/transformers/persian_text_processor.py**
2. **persian_processor.py**
3. **persian_text.py**
4. **multilingual_processor.py**

## ⚠️ نکات مهم

- spaCy مدل‌های پیش‌آموزش دیده دارد
- parsivar برای پردازش خاص فارسی بهتر است
- nltk 3.9+ امن و با crawl4ai سازگار است
- عملکرد ممکن است بهتر باشد

## 🧪 تست

پس از migration، تست‌های زیر را اجرا کنید:
```bash
python -m pytest tests/test_persian_text_processor.py -v
``` 