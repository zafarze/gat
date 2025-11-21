# D:\GAT\core\services.py (ОБНОВЛЕННАЯ ВЕРСИЯ ДЛЯ ЦЕНТРА ВОПРОСОВ)

import pandas as pd
from collections import defaultdict
from django.db import transaction
import re
from datetime import datetime
from .models import (
    Student, SchoolClass, GatTest, StudentResult, Subject, 
    BankQuestion, StudentAnswer, QuestionCount
)

def extract_test_date_from_excel(file):
    """
    Извлекает дату теста из Excel файла.
    """
    try:
        file.seek(0)
        
        # Вариант 1: из имени файла
        filename = file.name
        date_pattern = r'(\d{4})[_-](\d{1,2})[_-](\d{1,2})'
        match = re.search(date_pattern, filename)
        
        if match:
            year, month, day = match.groups()
            return datetime(int(year), int(month), int(day)).date()
        
        # Вариант 2: из содержимого Excel
        try:
            df = pd.read_excel(file, nrows=5)
            file.seek(0)
            
            for col in df.columns:
                if any(keyword in str(col).lower() for keyword in ['date', 'time', 'дата', 'время']):
                    if not pd.isna(df[col].iloc[0]):
                        date_value = df[col].iloc[0]
                        if isinstance(date_value, (datetime, pd.Timestamp)):
                            return date_value.date()
                        elif isinstance(date_value, str):
                            date_match = re.search(date_pattern, date_value)
                            if date_match:
                                year, month, day = date_match.groups()
                                return datetime(int(year), int(month), int(day)).date()
        except Exception as e:
            print(f"Warning: Could not extract date from Excel content: {e}")
            file.seek(0)
        
        return None
        
    except Exception as e:
        print(f"Error extracting date from Excel: {e}")
        return None

def process_student_upload(excel_file):
    """
    Обрабатывает загрузку студентов из Excel файла.
    """
    try:
        df = pd.read_excel(excel_file, dtype={'student_id': str})
    except Exception as e:
        return {'errors': [f"Ошибка чтения файла: {e}"]}
    
    df.columns = [str(col).strip().lower() for col in df.columns]
    required_columns = {'student_id', 'класс', 'фамилия_рус', 'имя_рус'}
    
    if not required_columns.issubset(df.columns):
        missing = required_columns - set(df.columns)
        return {'errors': [f"Отсутствуют обязательные колонки: {', '.join(missing)}"]}
    
    created_count, updated_count, skipped_count, errors = 0, 0, 0, []
    class_names = df['класс'].dropna().unique()
    classes_cache = {cls.name: cls for cls in SchoolClass.objects.filter(name__in=class_names)}
    
    for index, row in df.iterrows():
        student_id, class_name = row.get('student_id'), row.get('класс')
        if pd.isna(student_id) or pd.isna(class_name):
            skipped_count += 1
            continue
            
        school_class = classes_cache.get(str(class_name).strip())
        if not school_class:
            errors.append(f"Строка {index + 2}: Класс '{class_name}' не найден.")
            continue
            
        student_data = {
            'school_class': school_class, 
            'status': 'ACTIVE',
            'last_name_ru': str(row.get('фамилия_рус', '')).strip(),
            'first_name_ru': str(row.get('имя_рус', '')).strip(),
            'last_name_tj': str(row.get('фамилия_тадж', '')).strip(),
            'first_name_tj': str(row.get('имя_тадж', '')).strip(),
            'last_name_en': str(row.get('surname', '')).strip(),
            'first_name_en': str(row.get('name', '')).strip(),
        }
        
        try:
            _, created = Student.objects.update_or_create(
                student_id=str(student_id).strip(), 
                defaults=student_data
            )
            if created: 
                created_count += 1
            else: 
                updated_count += 1
        except Exception as e:
            errors.append(f"Строка {index + 2}: Ошибка сохранения студента ID {student_id}. {e}")
    
    return {
        "created": created_count, 
        "updated": updated_count, 
        "skipped": skipped_count, 
        "errors": errors
    }

@transaction.atomic
def process_student_results_upload(gat_test, excel_file):
    """
    ОБНОВЛЕННАЯ ВЕРСИЯ для обработки результатов с учетом BankQuestion и StudentAnswer.
    """
    try:
        excel_sheets = pd.read_excel(excel_file, sheet_name=None, dtype={'Code': str})
    except Exception as e:
        return False, f"Критическая ошибка чтения Excel-файла: {e}"

    parent_class = gat_test.school_class
    if not parent_class or parent_class.parent is not None:
        return False, "GAT-тест должен быть привязан к классу-параллели."

    # Создаем словарь для конвертации аббревиатур предметов в ID
    subject_abbr_map = {
        s.abbreviation.upper(): s.id
        for s in Subject.objects.all()
        if s.abbreviation
    }

    # Кэш для вопросов из банка (для оптимизации)
    question_cache = {}
    
    # Словарь для хранения всех результатов
    all_results = defaultdict(lambda: {
        'student': None,
        'scores_by_subject': defaultdict(dict),
        'answers': []  # Список для хранения ответов на вопросы
    })

    errors = []
    processed_rows = 0
    created_students = 0
    updated_students = 0

    # Обработка каждого листа в файле
    for sheet_name, df in excel_sheets.items():
        df.columns = [str(col).strip() for col in df.columns]
        required_cols = {'Code', 'Surname', 'Name', 'Section'}
        
        if not required_cols.issubset(df.columns):
            errors.append(f"На листе '{sheet_name}' отсутствуют обязательные колонки: {', '.join(required_cols - set(df.columns))}")
            continue

        # Обработка каждой строки (ученика) на листе
        for index, row in df.iterrows():
            student_id = row.get('Code')
            if pd.isna(student_id):
                continue

            processed_rows += 1

            # Находим или создаем ученика
            class_letter = str(row.get('Section', '')).strip()
            class_name = f"{parent_class.name}{class_letter}"

            school_class, _ = SchoolClass.objects.get_or_create(
                name=class_name,
                school=gat_test.school,
                defaults={'parent': parent_class}
            )

            student_defaults = {
                'school_class': school_class,
                'last_name_ru': str(row.get('Surname', '')).strip(),
                'first_name_ru': str(row.get('Name', '')).strip(),
                'status': 'ACTIVE'
            }
            
            student, created = Student.objects.update_or_create(
                student_id=student_id,
                defaults=student_defaults
            )
            
            if created: 
                created_students += 1
            else: 
                updated_students += 1

            all_results[student_id]['student'] = student

            # Разбираем ответы по предметам и вопросам
            for col_name, value in row.items():
                if '_' not in col_name or col_name in required_cols:
                    continue

                parts = col_name.split('_')
                if len(parts) < 2:
                    continue
                    
                subject_abbr = parts[0].upper()
                question_num_str = parts[1]

                if not question_num_str.isdigit():
                    continue

                if subject_abbr in subject_abbr_map:
                    subject_id = subject_abbr_map[subject_abbr]
                    
                    # Определяем, правильный ли ответ
                    is_correct = False
                    if not pd.isna(value):
                        try:
                            if int(value) == 1:
                                is_correct = True
                        except (ValueError, TypeError):
                            pass

                    # Сохраняем результат для общего балла
                    all_results[student_id]['scores_by_subject'][subject_id][question_num_str] = is_correct

                    # Сохраняем информацию для создания StudentAnswer
                    # Находим соответствующий вопрос из банка
                    cache_key = f"{subject_id}_{question_num_str}"
                    if cache_key not in question_cache:
                        # Ищем вопрос по предмету и порядковому номеру в тесте
                        questions = BankQuestion.objects.filter(
                            subject_id=subject_id,
                            gat_tests=gat_test
                        ).order_by('id')
                        
                        if questions.exists() and int(question_num_str) <= questions.count():
                            question_cache[cache_key] = questions[int(question_num_str) - 1]
                        else:
                            question_cache[cache_key] = None

                    question = question_cache[cache_key]
                    if question:
                        all_results[student_id]['answers'].append({
                            'question': question,
                            'is_correct': is_correct,
                            'chosen_option_order': 1 if is_correct else None  # Упрощенная логика
                        })

    # Сохранение результатов в базу данных
    for student_id, data in all_results.items():
        student_obj = data['student']
        scores_by_subject_dict = data['scores_by_subject']
        answers_data = data['answers']

        # Считаем итоговый балл
        total_score = sum(
            sum(1 for is_correct in answers.values() if is_correct)
            for answers in scores_by_subject_dict.values()
        )

        # Преобразуем ID предметов в строки для JSON
        scores_dict_str_keys = {str(k): v for k, v in scores_by_subject_dict.items()}

        # Создаем или обновляем StudentResult
        student_result, created = StudentResult.objects.update_or_create(
            student=student_obj,
            gat_test=gat_test,
            defaults={
                'total_score': total_score,
                'scores_by_subject': scores_dict_str_keys
            }
        )

        # Создаем записи StudentAnswer
        for answer_info in answers_data:
            StudentAnswer.objects.update_or_create(
                result=student_result,
                question=answer_info['question'],
                defaults={
                    'is_correct': answer_info['is_correct'],
                    'chosen_option_order': answer_info['chosen_option_order']
                }
            )

    report = {
        "processed_rows": processed_rows,
        "created_students": created_students,
        "updated_students": updated_students,
        "total_unique_students": len(all_results),
        "errors": errors
    }
    return True, report

def validate_question_counts(gat_test):
    """
    Проверяет соответствие количества вопросов в тесте настройкам QuestionCount.
    Возвращает словарь с предупреждениями.
    """
    warnings = []
    
    # Получаем вопросы теста, сгруппированные по предметам
    questions_by_subject = {}
    for question in gat_test.questions.all():
        subject_id = question.subject_id
        if subject_id not in questions_by_subject:
            questions_by_subject[subject_id] = 0
        questions_by_subject[subject_id] += 1
    
    # Проверяем соответствие настройкам
    for subject_id, actual_count in questions_by_subject.items():
        try:
            expected_count_obj = QuestionCount.objects.get(
                school_class=gat_test.school_class,
                subject_id=subject_id
            )
            expected_count = expected_count_obj.number_of_questions
            
            if actual_count != expected_count:
                subject = Subject.objects.get(id=subject_id)
                warnings.append(
                    f"По предмету {subject.name}: ожидается {expected_count} вопросов, "
                    f"фактически {actual_count}"
                )
                
        except QuestionCount.DoesNotExist:
            subject = Subject.objects.get(id=subject_id)
            warnings.append(
                f"Для предмета {subject.name} не настроено количество вопросов"
            )
    
    return warnings

def get_available_questions_for_test(gat_test, subject=None, topic=None, difficulty=None):
    """
    Возвращает доступные вопросы из банка для добавления в тест.
    """
    questions = BankQuestion.objects.filter(
        subject__in=gat_test.questions.values('subject').distinct(),
        school_class=gat_test.school_class
    ).exclude(
        gat_tests=gat_test
    )
    
    if subject:
        questions = questions.filter(subject=subject)
    
    if topic:
        questions = questions.filter(topic=topic)
        
    if difficulty:
        questions = questions.filter(difficulty=difficulty)
    
    return questions.select_related('subject', 'topic')

def generate_test_variant(gat_test, variant_name='A'):
    """
    Генерирует вариант теста с перемешанными вопросами и вариантами ответов.
    """
    questions = list(gat_test.questions.all())
    
    # Перемешиваем вопросы, если нужно
    if gat_test.shuffle_questions:
        import random
        random.shuffle(questions)
    
    variant_data = {
        'variant_name': variant_name,
        'test_name': gat_test.name,
        'questions': []
    }
    
    for question in questions:
        question_data = {
            'id': question.id,
            'text': question.text,
            'subject': question.subject.name,
            'options': []
        }
        
        options = list(question.options.all())
        
        # Перемешиваем варианты ответов, если нужно
        if gat_test.shuffle_options:
            import random
            random.shuffle(options)
        
        for i, option in enumerate(options, 1):
            question_data['options'].append({
                'order': i,
                'text': option.text,
                'is_correct': option.is_correct
            })
        
        variant_data['questions'].append(question_data)
    
    return variant_data