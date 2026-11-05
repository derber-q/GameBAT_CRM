"""Запуск независимого профиля, без запуска Django и без входящего HTTP-сервера."""
import argparse
import os
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox
from print_agent.__main__ import exclusive
from .configuration import profile_folder,private_folder
from .gui import Application


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--profile',default='default')
    parser.add_argument('--background',action='store_true')
    parser.add_argument('--self-test',type=Path)
    args=parser.parse_args()
    if os.environ.get('GAMEBAT_ENV')=='local_test':raise SystemExit('local_test: настоящий Local Agent запрещён.')
    if args.self_test:
        from .self_test import run
        run(args.self_test);return
    if sys.platform!='win32':raise SystemExit('ReSOURCE Local Agent предназначен для Windows.')
    folder=private_folder(profile_folder(args.profile))
    root=tk.Tk()
    try:
        with exclusive(folder/'application.lock'):
            app=Application(root,folder,args.profile)
            if args.background:root.withdraw()
            root.mainloop()
    except SystemExit:messagebox.showinfo('ReSOURCE','Этот профиль уже работает. Откройте его через значок в области уведомлений.')


if __name__=='__main__':main()
