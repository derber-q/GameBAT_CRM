#!/usr/bin/env python
"""Командная утилита Django для проекта GameBAT CRM."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GameBAT_CRM.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
