"""Ключ создаётся на Windows владельца; приватная часть не отправляется в CRM."""
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from . import configuration as store


def show(app):
    window=tk.Toplevel(app.root);window.title('Создать ключ восстановления')
    window.geometry('630x610');window.resizable(False,False);window.transient(app.root)
    frame=ttk.Frame(window,padding=26);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Ключ для восстановления CRM',font=('Segoe UI',17,'bold')).pack(anchor='w')
    ttk.Label(frame,text='Придумайте пароль и сохраните его отдельно.\nОн понадобится, если CRM придётся восстановить на другом компьютере.',
              wraplength=570).pack(anchor='w',pady=(10,18))
    folder=tk.StringVar(value=str(Path.home()/'ReSOURCE/Recovery'))
    ttk.Label(frame,text='Папка ключа').pack(anchor='w')
    ttk.Entry(frame,textvariable=folder).pack(fill='x',pady=5)
    def choose():
        selected=filedialog.askdirectory(parent=window,title='Папка ключа восстановления')
        if selected:folder.set(selected)
    ttk.Button(frame,text='Выбрать другую папку…',command=choose).pack(anchor='w',pady=(0,10))
    password=tk.StringVar();confirmation=tk.StringVar()
    ttk.Label(frame,text='Пароль · не меньше 12 символов').pack(anchor='w')
    entry=ttk.Entry(frame,textvariable=password,show='●');entry.pack(fill='x',pady=(5,10))
    ttk.Label(frame,text='Повторите пароль').pack(anchor='w')
    ttk.Entry(frame,textvariable=confirmation,show='●').pack(fill='x',pady=(5,12))
    saved=tk.BooleanVar(value=False);remember=tk.BooleanVar(value=True)
    ttk.Checkbutton(frame,text='Я сохранил этот пароль отдельно от CRM',variable=saved).pack(anchor='w',pady=5)
    ttk.Checkbutton(frame,text='Запомнить пароль в защищённом хранилище Windows',variable=remember).pack(anchor='w',pady=5)
    ttk.Label(frame,text='Приватный ключ остаётся у вас. После создания скопируйте папку\nключа на отдельный носитель. В CRM передаётся только публичный ключ.',
              foreground='#61758b',wraplength=570).pack(anchor='w',pady=14)
    def create():
        secret=password.get()
        if len(secret)<12 or secret!=confirmation.get():
            messagebox.showerror('Проверьте пароль','Пароли должны совпадать и содержать не меньше 12 символов.',parent=window);return
        if not saved.get():
            messagebox.showinfo('Сохраните пароль','Сначала сохраните пароль отдельно и отметьте это в форме.',parent=window);return
        try:
            directory=Path(folder.get()).absolute()
            if any((item/'.git').exists() for item in (directory,*directory.parents)):
                raise ValueError('Ключ нельзя сохранять в Git-репозитории.')
            directory=store.private_folder(directory)
            private=directory/'ReSOURCE.recovery.pem';public=directory/'ReSOURCE.public.pem'
            if private.exists() or public.exists():
                raise ValueError('В этой папке уже есть ключ. Выберите новую папку; прежний ключ сохранён.')
            from crm_backups.crypto import generate_keys
            private_bytes,public_bytes=generate_keys(secret.encode('utf-8'))
            for path,data in ((private,private_bytes),(public,public_bytes)):
                with path.open('xb') as stream:
                    store.private_file(path);stream.write(data);stream.flush();os.fsync(stream.fileno())
            with app.lock:
                config=dict(app.config)
                config['recovery_key_path'],config['recovery_public_path']=str(private),str(public)
                if remember.get():config['recovery_password']=secret
                else:config.pop('recovery_password',None)
                store.save(app.folder,config);app.config=config
            password.set('');confirmation.set('')
            window.destroy()
            messagebox.showinfo('Ключ создан','Ключ сохранён в '+str(directory)+'.\n\nТеперь передайте публичный ключ в настройки резервирования CRM.\nПриватный ключ и пароль серверу не передавайте.')
        except Exception as exc:
            messagebox.showerror('Ключ не создан',str(exc) if isinstance(exc,ValueError) else 'Не удалось сохранить ключ. Проверьте выбранную папку.',parent=window)
    ttk.Button(frame,text='Создать и сохранить ключ',style='Primary.TButton',command=create).pack(fill='x',pady=5)
    entry.focus_set()
    return window
