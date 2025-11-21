// D:\GAT\static\js\booklet.js

let bookletData = {};
try {
    bookletData = JSON.parse(document.getElementById('booklet-data').textContent);
} catch (e) { console.error('JSON Error', e); }

// --- Функция показа статуса ---
function showStatus(message, type) {
    const indicator = document.getElementById('save-status-indicator');
    if (!indicator) return;
    indicator.innerText = message;
    indicator.style.opacity = '1';
    if (type === 'error') indicator.style.borderLeftColor = '#ef4444';
    else if (type === 'success') {
        indicator.style.borderLeftColor = '#10b981';
        setTimeout(() => { indicator.style.opacity = '0'; }, 2000);
    } else {
        indicator.style.borderLeftColor = '#2563eb';
    }
}

// --- ГЛАВНАЯ ЛОГИКА ПАГИНАЦИИ (A4) ---
function paginateContent() {
    const sourceContainer = document.getElementById('source-container');
    // Берем все элементы (заголовки и вопросы)
    const items = Array.from(sourceContainer.children); 
    const root = document.getElementById('pages-root');
    
    // Очищаем root перед рендером
    root.innerHTML = ''; 

    let pageIndex = 1;
    let currentSheetObj = createNewSheet(pageIndex);
    let currentColumn = currentSheetObj.colLeft;
    let isLeftCol = true;

    items.forEach(item => {
        // Клонируем элемент из источника
        const el = item.cloneNode(true);
        
        // Добавляем во временное место
        currentColumn.appendChild(el);

        // --- ✨ УЛУЧШЕННАЯ ПРОВЕРКА ПЕРЕПОЛНЕНИЯ ✨ ---
        // Мы добавляем небольшой буфер (5px). Если контент влезает "впритык" или 
        // чуть-чуть вылезает, мы считаем, что он НЕ влез. Это спасает от обрезания нижних границ.
        const buffer = 5; 
        
        if (currentColumn.scrollHeight > currentColumn.clientHeight + buffer) {
            
            // Элемент НЕ ВЛЕЗ. Удаляем.
            currentColumn.removeChild(el);

            // Решаем, куда перенести
            if (isLeftCol) {
                // Переход в ПРАВУЮ колонку
                isLeftCol = false;
                currentColumn = currentSheetObj.colRight;
            } else {
                // Переход на НОВУЮ СТРАНИЦУ
                pageIndex++;
                currentSheetObj = createNewSheet(pageIndex);
                isLeftCol = true;
                currentColumn = currentSheetObj.colLeft;
            }

            // Добавляем в новую колонку
            currentColumn.appendChild(el);
        }
    });

    // Инициализация функционала
    initSortable();
    renumberQuestions();
    reletterAllOptions();
}

// --- Создание HTML разметки листа ---
function createNewSheet(pageNum) {
    const root = document.getElementById('pages-root');
    
    const headerTmpl = document.getElementById('header-template').content.cloneNode(true);
    const footerTmpl = document.getElementById('footer-template').content.cloneNode(true);
    footerTmpl.querySelector('.page-number').textContent = pageNum;

    const sheet = document.createElement('div');
    sheet.className = 'sheet';
    sheet.id = `sheet-${pageNum}`;

    const headerDiv = document.createElement('div');
    headerDiv.className = 'sheet-header';
    headerDiv.appendChild(headerTmpl);

    const bodyDiv = document.createElement('div');
    bodyDiv.className = 'sheet-body';
    
    const colLeft = document.createElement('div');
    colLeft.className = 'sheet-column col-left';
    
    const separator = document.createElement('div');
    separator.className = 'vertical-separator';

    const colRight = document.createElement('div');
    colRight.className = 'sheet-column col-right';

    bodyDiv.append(colLeft, separator, colRight);

    const footerDiv = document.createElement('div');
    footerDiv.className = 'sheet-footer';
    footerDiv.appendChild(footerTmpl);

    sheet.append(headerDiv, bodyDiv, footerDiv);
    root.appendChild(sheet);

    return { sheet, colLeft, colRight, bodyDiv };
}

// --- Нумерация вопросов (сквозная) ---
function renumberQuestions() {
    let globalIndex = 1;
    document.querySelectorAll('#pages-root .question-item').forEach(q => {
        const numSpan = q.querySelector('.q-num');
        if(numSpan) numSpan.textContent = globalIndex + '.';
        globalIndex++;
    });
}

// --- Буквы ответов (A, B, C...) ---
function reletterAllOptions() {
    const letters = ['A', 'B', 'C', 'D', 'E', 'F'];
    document.querySelectorAll('.q-body ul').forEach(list => {
        list.querySelectorAll('.opt').forEach((span, index) => { 
            span.textContent = letters[index] + ')'; 
        });
    });
}

// --- Drag-and-Drop (Sortable) ---
function initSortable() {
    const columns = document.querySelectorAll('.sheet-column');
    columns.forEach(col => {
        new Sortable(col, {
            group: 'shared-columns', 
            animation: 150,
            handle: '.content-element', // Можно тащить и за вопросы, и за заголовки
            ghostClass: 'sortable-ghost',
            onEnd: (evt) => {
                const item = evt.item;
                
                // ✨ ЛОГИКА ПЕРЕТАСКИВАНИЯ ПРЕДМЕТОВ ✨
                if (item.dataset.type === 'title') {
                    handleSubjectMove(item);
                } else {
                    // Если перетащили просто вопрос - просто перенумеровываем
                    renumberQuestions();
                    saveOrder();
                }
            }
        });
    });
	function handleSubjectMove(headerItem) {
    const subjectId = headerItem.dataset.subjectId;
    if (!subjectId) return;

    showStatus('Перегруппировка...', 'saving');

    // 1. Собираем все элементы со всех страниц в один плоский список
    // В том порядке, как они сейчас визуально расположены
    let allElements = [];
    document.querySelectorAll('.sheet-column').forEach(col => {
        Array.from(col.children).forEach(child => allElements.push(child));
    });

    // 2. Находим индекс, куда упал заголовок
    const headerIndex = allElements.indexOf(headerItem);

    // 3. Находим все вопросы ЭТОГО предмета
    const subjectQuestions = allElements.filter(el => 
        el.dataset.type === 'question' && el.dataset.subjectId === subjectId
    );

    // 4. Удаляем вопросы из их старых мест в массиве
    // (Важно делать это аккуратно, чтобы не сбить индексы)
    allElements = allElements.filter(el => 
        !(el.dataset.type === 'question' && el.dataset.subjectId === subjectId)
    );

    // 5. Вставляем вопросы сразу после заголовка
    // headerItem теперь находится где-то в новом массиве allElements (потому что мы удалили вопросы)
    const newHeaderIndex = allElements.indexOf(headerItem);
    
    // Вставляем вопросы (splice изменяет массив на месте)
    // Аргументы: куда вставлять, сколько удалять (0), ...что вставлять
    allElements.splice(newHeaderIndex + 1, 0, ...subjectQuestions);

    // 6. Теперь нам нужно вернуть этот порядок в DOM source-container и ПЕРЕРИСОВАТЬ страницы
    const sourceContainer = document.getElementById('source-container');
    sourceContainer.innerHTML = ''; // Очищаем источник
    
    allElements.forEach(el => {
        // Важно: нам нужны ОРИГИНАЛЫ или чистые клоны. 
        // Но проще всего просто вернуть эти элементы в sourceContainer.
        // При paginateContent они будут клонироваться заново.
        sourceContainer.appendChild(el);
    });

    // 7. Запускаем полную переверстку буклета
    paginateContent();
    
    // 8. Сохраняем новый порядок
    saveOrder();
    showStatus('Предмет перемещен', 'success');
}
    
    // Сортировка внутри вариантов ответов (если нужно менять порядок A/B/C)
    document.querySelectorAll('.q-body ul').forEach(list => {
        new Sortable(list, {
            animation: 150, 
            handle: '.option-label',
            onEnd: (evt) => {
                reletterAllOptions(); 
                saveOptionOrder(list);
            }
        });
    });
}

// --- Сохранение порядка вопросов ---
async function saveOrder() {
    showStatus('Сохранение...', 'saving');
    const allQuestions = document.querySelectorAll('#pages-root .question-item');
    const ids = Array.from(allQuestions)
        .map(div => div.getAttribute('data-id'))
        .filter(id => id);

    try {
        const res = await fetch(bookletData.saveUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': bookletData.csrfToken },
            body: JSON.stringify({ order: ids })
        });
        if (res.ok) showStatus('Порядок сохранен', 'success');
        else showStatus('Ошибка сохранения', 'error');
    } catch (e) { showStatus('Ошибка сети', 'error'); }
}

// --- Сохранение порядка вариантов ---
async function saveOptionOrder(listElement) {
    const questionId = listElement.closest('.question-item')?.dataset.id;
    if (!questionId) return;
    const optionIds = Array.from(listElement.querySelectorAll('li[data-id]')).map(li => li.dataset.id);
    const url = bookletData.saveOptionOrderUrl.replace('0', questionId);
    try {
        await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': bookletData.csrfToken },
            body: JSON.stringify({ order: optionIds })
        });
        showStatus('Варианты сохранены', 'success');
    } catch (e) { console.error(e); }
}

// --- Cropper (Обрезка) ---
let cropper;
let currentImageElement;
let currentQuestionId;

window.openCropper = function(container, questionId) {
    currentImageElement = container.querySelector('img');
    currentQuestionId = questionId;
    const modal = document.getElementById('cropper-modal');
    const imageToCrop = document.getElementById('image-to-crop');
    modal.style.display = 'block';
    imageToCrop.src = currentImageElement.src;

    if (cropper) { cropper.destroy(); }
    imageToCrop.onload = function() {
        cropper = new Cropper(imageToCrop, {
            viewMode: 1, dragMode: 'move', autoCropArea: 0.8, restore: false,
            guides: true, center: true, highlight: false, cropBoxMovable: true, cropBoxResizable: true
        });
    };
};

document.getElementById('btn-cancel-crop').addEventListener('click', () => {
    document.getElementById('cropper-modal').style.display = 'none';
    if (cropper) { cropper.destroy(); cropper = null; }
});

document.getElementById('btn-save-crop').addEventListener('click', () => {
    if (!cropper) return;
    showStatus('Загрузка...', 'saving');
    cropper.getCroppedCanvas().toBlob((blob) => {
        const formData = new FormData();
        formData.append('image', blob, 'cropped.jpg');
        const url = bookletData.updateImageUrl.replace('0', currentQuestionId);

        fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': bookletData.csrfToken },
            body: formData
        })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') {
                currentImageElement.src = data.url + '?t=' + new Date().getTime();
                document.getElementById('cropper-modal').style.display = 'none';
                cropper.destroy();
                showStatus('Фото обновлено', 'success');
            } else showStatus(data.message, 'error');
        });
    }, 'image/jpeg', 0.9);
});

// --- УМНАЯ СЕТКА ДЛЯ ОТВЕТОВ ---
function optimizeAnswerLayout() {
    const MAX_CHARS_FOR_GRID = 35; 
    const questionLists = document.querySelectorAll('#source-container .q-body ul');

    questionLists.forEach(list => {
        const options = Array.from(list.querySelectorAll('.option-text'));
        const hasLongOption = options.some(span => span.textContent.trim().length > MAX_CHARS_FOR_GRID);

        if (!hasLongOption && options.length > 0) {
            list.classList.add('smart-grid');
        } else {
            list.classList.remove('smart-grid');
        }
    });
}

// --- ЗАПУСК ---
window.onload = () => {
    console.log("Resources loaded. Starting pagination...");
    
    // 1. Сначала оптимизируем сетку ответов
    optimizeAnswerLayout(); 
    
    // 2. Небольшая задержка для рендеринга шрифтов
    setTimeout(() => {
        paginateContent();
        console.log("Pagination complete.");
    }, 100);
};

// --- ✨ НОВАЯ ФУНКЦИЯ СОХРАНЕНИЯ ТЕКСТА ✨ ---
async function saveText(element, type, id) {
    const newText = element.innerText.trim(); // Берем чистый текст
    
    // Определяем URL в зависимости от того, что редактируем (вопрос или вариант)
    // Используем хардкод URL pattern, так как мы не можем передать все ID через json_script
    // Убедитесь, что эти URL совпадают с вашим urls.py!
    let url = '';
    if (type === 'question') {
        url = `/api/bank-questions/${id}/quick-edit/`;
    } else if (type === 'option') {
        url = `/api/bank-options/${id}/quick-edit/`;
    }

    if (!url) return;

    showStatus('Сохранение...', 'saving');

    try {
        // Создаем FormData, как будто отправили обычную форму
        const formData = new FormData();
        formData.append('text', newText);

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': bookletData.csrfToken // Берем токен из глобальной переменной
            },
            body: formData
        });

        if (response.ok) {
            showStatus('Сохранено', 'success');
            element.style.backgroundColor = '#dcfce7'; // Зеленая вспышка
            setTimeout(() => element.style.backgroundColor = '', 500);
        } else {
            showStatus('Ошибка сохранения', 'error');
            console.error('Save failed', response.status);
        }
    } catch (error) {
        showStatus('Ошибка сети', 'error');
        console.error('Network error', error);
    }
}

// Функция переключения отображения правильных ответов
function toggleAnswers() {
    const isShowing = document.body.classList.contains('show-correct-answers');
    const btn = document.querySelector('.btn-answers');
    
    if (isShowing) {
        // Скрыть
        document.body.classList.remove('show-correct-answers');
        btn.innerHTML = '👁️ Показать ответы';
        
        // Убираем классы с элементов
        document.querySelectorAll('li[data-is-correct="true"]').forEach(li => {
            li.classList.remove('correct-answer-highlight');
        });
    } else {
        // Показать
        document.body.classList.add('show-correct-answers');
        btn.innerHTML = '🙈 Скрыть ответы';
        
        // Добавляем классы
        document.querySelectorAll('li[data-is-correct="true"]').forEach(li => {
            li.classList.add('correct-answer-highlight');
        });
    }
}

// --- RESIZE LOGIC (Изменение размера картинки) ---
let isResizing = false;
let currentResizerParams = {};

function initResize(e, questionId) {
    e.stopPropagation(); // Чтобы не сработал клик по картинке (Cropper)
    e.preventDefault();  // Чтобы не выделялся текст
    
    const container = e.target.closest('.editable-image-container');
    
    isResizing = true;
    currentResizerParams = {
        startX: e.clientX,
        startWidth: container.offsetWidth,
        container: container,
        questionId: questionId
    };

    // Добавляем слушатели на весь документ, чтобы можно было увести мышь за пределы картинки
    document.addEventListener('mousemove', doResize);
    document.addEventListener('mouseup', stopResize);
}

function doResize(e) {
    if (!isResizing) return;
    
    // Вычисляем новую ширину
    const dx = e.clientX - currentResizerParams.startX;
    const newWidthPx = currentResizerParams.startWidth + dx;
    
    // Переводим в проценты относительно родителя (чтобы было адаптивно)
    const parentWidth = currentResizerParams.container.parentElement.offsetWidth;
    let newWidthPercent = (newWidthPx / parentWidth) * 100;

    // Ограничения (мин 10%, макс 100%)
    if (newWidthPercent < 10) newWidthPercent = 10;
    if (newWidthPercent > 100) newWidthPercent = 100;

    currentResizerParams.container.style.width = newWidthPercent + '%';
}

function stopResize(e) {
    if (!isResizing) return;
    isResizing = false;
    
    document.removeEventListener('mousemove', doResize);
    document.removeEventListener('mouseup', stopResize);

    // Сохраняем новую ширину в базу
    saveImageWidth(currentResizerParams.questionId, currentResizerParams.container.style.width);
}

async function saveImageWidth(questionId, widthVal) {
    showStatus('Сохранение размера...', 'saving');
    
    // Формируем URL (предполагаем, что паттерн URL такой же, как для text edit)
    // Вам нужно добавить этот URL в шаблон booklet.html в блок booklet-data или хардкодить
    const url = `/api/bank-questions/${questionId}/save-width/`; 
    
    try {
        const formData = new FormData();
        formData.append('width', widthVal);

        const res = await fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': bookletData.csrfToken },
            body: formData
        });

        if (res.ok) showStatus('Размер сохранен', 'success');
        else showStatus('Ошибка сохранения', 'error');
    } catch (e) {
        console.error(e);
        showStatus('Ошибка сети', 'error');
    }
}

// --- Переключение Ч/Б режима ---
window.toggleGrayscale = function() {
    // Добавляем/удаляем класс на body
    const isGray = document.body.classList.toggle('grayscale-preview');
    
    const btn = document.querySelector('.btn-bw');
    if (isGray) {
        btn.innerHTML = '🌈 Цветной вид';
        btn.style.backgroundColor = '#db2777'; // Розовый или любой яркий, чтобы заметно было
        showStatus('Включен режим Ч/Б печати', 'success');
    } else {
        btn.innerHTML = '⚫⚪ Ч/Б вид';
        btn.style.backgroundColor = ''; // Сброс цвета
    }
};