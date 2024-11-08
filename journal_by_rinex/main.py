#!/usr/bin/env python3

import tkinter as tk
from tkinter import filedialog, messagebox
import os

from .functions import get_info, journal_generator

class FileProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Приложение для обработки файлов")
        self.files = []
        self.save_path = ""

        # Переменные для текстовых параметров
        self.organization = tk.StringVar(value='Введите название организации')
        self.object_name = tk.StringVar(value='Введите название объекта')
        self.operator = tk.StringVar(value='Введите ФИО исполнителя')
        self.benchmark_type = tk.StringVar(value='Введите тип и характеристику центра (марки)')
        self.center_type = tk.StringVar(value='Введите тип и характеристику геодезического знака')
        self.gdop = tk.StringVar(value='Введите GDOP')
        self.pdop = tk.StringVar(value='Введите PDOP')

        # Переменная для Radiobutton выбора
        self.measurement_type = tk.StringVar(value="Без штатива до основания")  # Установка значения по умолчанию

        # Создание интерфейса
        self.create_widgets()

    def create_widgets(self):
        # Поля ввода для текстовых параметров
        self.create_text_input("Организация", self.organization, 0)
        self.create_text_input("Объект", self.object_name, 1)
        self.create_text_input("Исполнитель", self.operator, 2)
        self.create_text_input("Тип и характеристика геодезического знака", self.benchmark_type, 3)
        self.create_text_input("Тип и характеристика центра (марки)", self.center_type, 4)
        self.create_text_input("GDOP", self.gdop, 5)
        self.create_text_input("PDOP", self.pdop, 6)

        # Радиокнопки для выбора типа измерения
        tk.Label(self.root, text="Тип измерения:").grid(row=7, column=0, sticky=tk.W, padx=10, pady=5)
        
        measurement_options = [
            "Без штатива до основания",
            "Без штатива до фазового центра",
            "На штативе наклонная",
            "На штативе до основания",
            "На штативе до фазового центра"
        ]
        
        for idx, option in enumerate(measurement_options):
            tk.Radiobutton(
                self.root, text=option, variable=self.measurement_type, value=option
            ).grid(row=8 + idx, column=0, columnspan=2, sticky=tk.W, padx=10)

        # Кнопка для добавления файлов
        self.add_files_button = tk.Button(self.root, text="Добавить файлы", command=self.add_files)
        self.add_files_button.grid(row=13, column=0, columnspan=2, pady=10)

        # Кнопка для выбора папки сохранения
        self.save_path_button = tk.Button(self.root, text="Выбрать путь для сохранения", command=self.select_save_path)
        self.save_path_button.grid(row=14, column=0, columnspan=2, pady=10)

        # Кнопка для выполнения обработки
        self.process_button = tk.Button(self.root, text="Обработать файлы", command=self.process_files)
        self.process_button.grid(row=15, column=0, columnspan=2, pady=20)

        # Поле для отображения добавленных файлов
        self.files_list_label = tk.Label(self.root, text="Выбранные файлы:")
        self.files_list_label.grid(row=16, column=0, columnspan=2)
        self.files_list_text = tk.Text(self.root, height=10, width=50, state='disabled')
        self.files_list_text.grid(row=17, column=0, columnspan=2, pady=5)

        # Поле для отображения пути сохранения
        self.save_path_label = tk.Label(self.root, text="Путь для сохранения:")
        self.save_path_label.grid(row=18, column=0, columnspan=2)
        self.save_path_text = tk.Entry(self.root, width=50, state='disabled')
        self.save_path_text.grid(row=19, column=0, columnspan=2, pady=5)

    def create_text_input(self, label_text, variable, row):
        """Создает текстовое поле с меткой."""
        label = tk.Label(self.root, text=label_text)
        label.grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        entry = tk.Entry(self.root, textvariable=variable, width=40)
        entry.grid(row=row, column=1, padx=10, pady=5)

    def add_files(self):
        # Открытие диалога для выбора файлов
        new_files = filedialog.askopenfilenames(title="Выберите файлы", filetypes=(("Все файлы", "*.*"),))
        self.files.extend(new_files)
        self.update_files_list()

    def select_save_path(self):
        # Открытие диалога для выбора папки
        self.save_path = filedialog.askdirectory(title="Выберите папку для сохранения")
        self.update_save_path()

    def update_files_list(self):
        # Обновление списка файлов в интерфейсе
        self.files_list_text.config(state='normal')
        self.files_list_text.delete(1.0, tk.END)
        for file in self.files:
            self.files_list_text.insert(tk.END, file + "\n")
        self.files_list_text.config(state='disabled')

    def update_save_path(self):
        # Обновление поля пути сохранения в интерфейсе
        self.save_path_text.config(state='normal')
        self.save_path_text.delete(0, tk.END)
        self.save_path_text.insert(0, self.save_path)
        self.save_path_text.config(state='disabled')

    def process_files(self):
        if not self.files:
            messagebox.showwarning("Нет файлов", "Пожалуйста, добавьте файлы для обработки.")
            return

        if not self.save_path:
            messagebox.showwarning("Нет пути для сохранения", "Пожалуйста, укажите путь для сохранения.")
            return

        # Получение значений текстовых параметров и типа измерения
        metadata = {
            "Организация": self.organization.get(),
            "Объект": self.object_name.get(),
            "Исполнитель": self.operator.get(),
            "Тип и характеристика геодезического знака": self.benchmark_type.get(),
            "Тип и характеристика центра (марки)": self.center_type.get(),
            "GDOP": self.gdop.get(),
            "PDOP": self.pdop.get(),
            "Тип измерения": self.measurement_type.get()
        }

        # Пример обработки файлов
        for file in self.files:
            filename = os.path.basename(file)

            file_info = get_info(file)
            match self.measurement_type.get():
                case 'Без штатива до основания':
                    file_info['antenna height type'] = 'base'
                case 'Без штатива до фазового центра':
                    file_info['antenna height type'] = 'phase'
                case 'На штативе наклонная':
                    file_info['antenna height type'] = 'tripod_slant'
                case 'На штативе до основания':
                    file_info['antenna height type'] = 'tripod_base'
                case 'На штативе до фазового центра':
                    file_info['antenna height type'] = 'tripod_phase'

            file_info['organization'] = metadata['Организация']
            file_info['object'] = metadata['Объект']
            file_info['operator'] = metadata['Исполнитель']
            file_info['centre type'] = metadata['Тип и характеристика геодезического знака']
            file_info['benchmark type'] = metadata['Тип и характеристика центра (марки)']
            file_info['gdop'] = metadata['GDOP']
            file_info['pdop'] = metadata['PDOP']

            save_file = os.path.join(self.save_path, file_info['marker name'].strip())
            journal_generator(file_info, save_file)

        messagebox.showinfo("Обработка завершена", "Файлы успешно обработаны и сохранены.")
        self.files.clear()
        self.update_files_list()
        self.save_path = ""
        self.update_save_path()

def run_app():
    root = tk.Tk()
    app = FileProcessorApp(root)
    root.mainloop()

if __name__ == "__main__":
    run_app()
