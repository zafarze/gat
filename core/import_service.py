import pandas as pd
from docx import Document
from django.db import transaction
from django.core.files.base import ContentFile
from .models import BankQuestion, BankAnswerOption

def process_import(file, file_type, topic, user):
    if file_type == 'excel':
        return _import_from_excel(file, topic, user)
    elif file_type == 'word':
        return _import_from_word(file, topic, user)
    else:
        return 0, ["Неподдерживаемый формат файла"]

# --- 1. EXCEL (Без изменений) ---
def _import_from_excel(file, topic, user):
    try:
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip().str.lower()
    except Exception as e:
        return 0, [f"Ошибка чтения Excel: {e}"]

    created_count = 0
    errors = []

    col_q = next((c for c in df.columns if 'вопрос' in c or 'question' in c), None)
    col_correct = next((c for c in df.columns if 'правильный' in c or 'correct' in c), None)
    cols_wrong = [c for c in df.columns if 'option' in c or 'вариант' in c or 'неверн' in c or 'wrong' in c]

    if not col_q or not col_correct:
        return 0, ["В файле нет колонок 'Вопрос' или 'Правильный ответ'."]

    for index, row in df.iterrows():
        try:
            text = str(row[col_q]).strip()
            correct_text = str(row[col_correct]).strip()
            if not text or text == 'nan': continue

            with transaction.atomic():
                question = BankQuestion.objects.create(
                    topic=topic, subject=topic.subject, school_class=topic.school_class,
                    text=text, author=user, difficulty='MEDIUM'
                )
                BankAnswerOption.objects.create(question=question, text=correct_text, is_correct=True)
                for col_w in cols_wrong:
                    wrong_text = str(row[col_w]).strip()
                    if wrong_text and wrong_text != 'nan' and wrong_text != correct_text:
                         BankAnswerOption.objects.create(question=question, text=wrong_text, is_correct=False)
            created_count += 1
        except Exception as e:
            errors.append(f"Ошибка в строке {index+2}: {e}")
    return created_count, errors

# --- 2. WORD (С картинками везде) ---

def _extract_image_from_paragraph(paragraph, doc):
    """Ищет картинку в параграфе."""
    for run in paragraph.runs:
        if 'drawing' in run.element.xml:
            blips = run.element.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
            for blip in blips:
                embed = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                if embed:
                    image_part = doc.part.related_parts[embed]
                    image_bytes = image_part._blob
                    content_type = image_part.content_type
                    ext = content_type.split('/')[-1] if '/' in content_type else 'jpg'
                    filename = f"img.{ext}"
                    return image_bytes, filename
    return None, None

def _import_from_word(file, topic, user):
    try:
        doc = Document(file)
    except Exception as e:
        return 0, [f"Ошибка чтения Word: {e}"]

    created_count = 0
    errors = []
    
    # Данные текущего вопроса
    current_q_text = None
    current_q_image = None
    current_opts = [] # Список словарей: {'text': str, 'is_correct': bool, 'image': (bytes, name)}

    def save_q():
        nonlocal current_q_text, current_q_image, current_opts, created_count
        if current_q_text and len(current_opts) >= 2:
            try:
                with transaction.atomic():
                    # 1. Сохраняем вопрос
                    q = BankQuestion.objects.create(
                        topic=topic, subject=topic.subject, school_class=topic.school_class,
                        text=current_q_text, author=user
                    )
                    if current_q_image:
                        q.question_image.save(current_q_image[1], ContentFile(current_q_image[0]), save=True)

                    # 2. Сохраняем варианты ответов
                    for opt in current_opts:
                        option_obj = BankAnswerOption.objects.create(
                            question=q, text=opt['text'], is_correct=opt['is_correct']
                        )
                        # Если у варианта есть картинка -> сохраняем её
                        if opt['image']:
                            option_obj.option_image.save(opt['image'][1], ContentFile(opt['image'][0]), save=True)
                            
                created_count += 1
            except Exception as e:
                errors.append(f"Ошибка вопроса '{current_q_text[:15]}...': {e}")
        
        # Очистка
        current_q_text = None
        current_q_image = None
        current_opts = []

    for para in doc.paragraphs:
        text = para.text.strip()
        image_data = _extract_image_from_paragraph(para, doc) # (bytes, filename) или (None, None)

        # Пустая строка без картинки -> пропускаем
        if not text and not image_data[0]:
            continue

        # --- ЭТО ВАРИАНТ ОТВЕТА? (+/-) ---
        if text.startswith('+') or text.startswith('-'):
            is_correct = text.startswith('+')
            clean_text = text[1:].strip()
            
            # Добавляем новый вариант в список
            current_opts.append({
                'text': clean_text,
                'is_correct': is_correct,
                'image': image_data if image_data[0] else None # Если картинка на той же строке
            })

        # --- ЭТО ВОПРОС? (Текст без маркеров) ---
        elif text:
            # Если уже есть накопленные ответы -> значит начался НОВЫЙ вопрос -> сохраняем старый
            if current_opts:
                save_q()

            if current_q_text:
                # Если текст вопроса идет в несколько абзацев, склеиваем
                current_q_text += "\n" + text
            else:
                current_q_text = text
            
            # Если в строке вопроса есть картинка
            if image_data[0]:
                current_q_image = image_data

        # --- ЭТО ПРОСТО КАРТИНКА (БЕЗ ТЕКСТА) ---
        elif image_data[0]:
            # Куда её прикрепить?
            
            if current_opts:
                # Если уже есть варианты ответов -> крепим к ПОСЛЕДНЕМУ варианту
                # (Логика: текст ответа, а под ним картинка)
                current_opts[-1]['image'] = image_data
            else:
                # Если вариантов еще нет -> крепим к ВОПРОСУ
                current_q_image = image_data

    save_q() # Сохраняем последний вопрос
    return created_count, errors