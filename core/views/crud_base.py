# D:\GAT\core\views\crud_base.py (ИСПРАВЛЕННЫЙ ФАЙЛ)

import json
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.generic import FormView, ListView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.template.loader import render_to_string
from .permissions import get_accessible_schools

# =============================================================================
# --- БАЗОВЫЕ КЛАССЫ С ЛОГИКОЙ HTMX ---
# =============================================================================

class HtmxListView(LoginRequiredMixin, ListView):
    template_name_prefix = None

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Общая логика прав доступа для списков
        if not user.is_staff and not user.is_superuser:
            if hasattr(self.model, 'school'):
                accessible_schools = get_accessible_schools(user)
                qs = qs.filter(school__in=accessible_schools)
            elif hasattr(self.model, 'school_class'):
                accessible_schools = get_accessible_schools(user)
                qs = qs.filter(school_class__school__in=accessible_schools)
        return qs

    def get_template_names(self):
        if self.request.htmx:
            # Обновляем всю страницу, если пришел сигнал 'force-refresh'
            if self.request.headers.get('HX-Trigger') == 'force-refresh':
                return [f'{self.template_name_prefix}/list.html']
            # В остальных случаях (фильтрация, пагинация) обновляем только таблицу
            return [f'{self.template_name_prefix}/_table.html']
        return [f'{self.template_name_prefix}/list.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'object_list' in context:
            context['items'] = context.pop('object_list')
        return context

class HtmxCreateView(LoginRequiredMixin, CreateView):
    template_name_prefix = None
    list_url_name = None

    def get_template_names(self):
        if self.request.htmx:
            return [f'{self.template_name_prefix}/form_modal.html']
        return [f'{self.template_name_prefix}/form.html']

    def form_valid(self, form):
        self.object = form.save()
        success_message = f'"{self.object}" успешно создан.'
        messages.success(self.request, success_message)

        if self.request.htmx:
            # УЛУЧШЕНИЕ: Отправляем сигнал 'force-refresh', чтобы список сам себя обновил
            trigger = {
                "close-modal": True,
                "show-message": {"text": success_message, "type": "success"},
                "force-refresh": True # Говорим списку обновиться
            }
            headers = {'HX-Trigger': json.dumps(trigger)}
            return HttpResponse(status=204, headers=headers)

        return redirect(reverse_lazy(self.list_url_name))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Добавить: {self.model._meta.verbose_name}'
        context['cancel_url'] = reverse_lazy(self.list_url_name)
        return context

    def form_invalid(self, form):
        if self.request.htmx:
            # При ошибке валидации просто перерисовываем содержимое модального окна
            context = self.get_context_data(form=form) # Получаем контекст с формой
            # Используем _form_content.html, если он есть, иначе form_modal.html
            template_to_render = f'{self.template_name_prefix}/partials/_form_content.html'
            # Проверка существования шаблона может быть добавлена здесь, если нужно
            # try:
            #     render_to_string(template_to_render, context)
            # except TemplateDoesNotExist:
            #     template_to_render = f'{self.template_name_prefix}/form_modal.html'
            response = render(self.request, template_to_render, context)
            response.status_code = 422 # Unprocessable Entity
            return response
        return super().form_invalid(form)

class HtmxFormView(LoginRequiredMixin, FormView):
    template_name_prefix = None
    list_url_name = None

    def get_template_names(self):
        if self.request.htmx:
            return [f'{self.template_name_prefix}/form_modal.html']
        return [f'{self.template_name_prefix}/form.html']

    def form_valid(self, form):
        raise NotImplementedError("You must implement form_valid in a subclass.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Форма"
        context['cancel_url'] = reverse_lazy(self.list_url_name)
        return context

    def form_invalid(self, form):
        if self.request.htmx:
            # При ошибке перерисовываем модальное окно целиком
            response = render(self.request, self.get_template_names()[0], self.get_context_data(form=form))
            response.status_code = 422 # Unprocessable Entity
            return response
        return super().form_invalid(form)

class HtmxUpdateView(LoginRequiredMixin, UpdateView): # <-- Правильное определение HtmxUpdateView
    template_name_prefix = None
    list_url_name = None
    # template_name можно переопределить в дочернем классе

    def get_template_names(self):
        # Если задан template_name, используем его
        if hasattr(self, 'template_name') and self.template_name:
             # Для HTMX ищем partials/_form_content.html или используем основной
             if self.request.htmx:
                 partial_template = f'{self.template_name_prefix}/partials/_form_content.html'
                 # Можно добавить проверку существования шаблона
                 return [partial_template] # При ошибке просто перерисовываем контент
             return [self.template_name]

        # Логика по умолчанию, если template_name не задан
        if self.request.htmx:
            return [f'{self.template_name_prefix}/form_modal.html']
        return [f'{self.template_name_prefix}/form.html']

    def form_valid(self, form):
        self.object = form.save()
        success_message = f'"{self.object}" успешно обновлен.'
        messages.success(self.request, success_message)

        if self.request.htmx:
            # УЛУЧШЕНИЕ: Отправляем сигнал 'force-refresh'
            trigger = {
                "close-modal": True,
                "show-message": {"text": success_message, "type": "success"},
                "force-refresh": True
            }
            headers = {'HX-Trigger': json.dumps(trigger)}
            return HttpResponse(status=204, headers=headers)

        return redirect(reverse_lazy(self.list_url_name))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Устанавливаем title только если он еще не установлен дочерним классом
        context.setdefault('title', f'Редактировать: {self.object}')
        context.setdefault('cancel_url', reverse_lazy(self.list_url_name))
        return context

    def form_invalid(self, form):
        if self.request.htmx:
             # При ошибке перерисовываем контент модального окна или всю страницу сборки
             template_names = self.get_template_names() # Получаем правильный шаблон
             response = render(self.request, template_names[0], self.get_context_data(form=form))
             response.status_code = 422 # Unprocessable Entity
             return response
        return super().form_invalid(form)

class HtmxDeleteView(LoginRequiredMixin, DeleteView):
    template_name_prefix = None
    list_url_name = None
    # template_name для окна подтверждения можно переопределить

    def get_template_names(self):
         # Для GET запроса (показ окна подтверждения)
         if self.request.method == 'GET' and hasattr(self, 'template_name') and self.template_name:
             return [self.template_name]
         # По умолчанию
         return [f'{self.template_name_prefix}/confirm_delete.html']

    def get_success_url(self):
        return reverse_lazy(self.list_url_name)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault('title', f'Удалить: {self.object}')
        context.setdefault('cancel_url', reverse_lazy(self.list_url_name))
        return context

    def post(self, request, *args, **kwargs):
        if self.request.htmx:
            self.object = self.get_object()
            item_name = str(self.object)
            self.object.delete()
            success_message = f'"{item_name}" успешно удален.'
            messages.error(self.request, success_message) # Используем error для красного сообщения

            # УЛУЧШЕНИЕ: Отправляем сигнал 'force-refresh'
            trigger = {
                "close-delete-modal": True,
                "show-message": {"text": success_message, "type": "error"},
                "force-refresh": True
            }
            headers = {'HX-Trigger': json.dumps(trigger)}
            return HttpResponse(status=204, headers=headers)

        # Стандартный POST для не-HTMX запросов
        return super().post(request, *args, **kwargs)