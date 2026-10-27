"""Актуальный сквозной сценарий рейса перенесён в arrival_browser_checks.

Прежняя форма отдельных валютных курсов и индивидуальная финализация
рейсового прихода заменены общей фиксацией прибытия и затрат.
"""
from .arrival_browser_checks import ArrivalBrowserChecks as TripOperationBrowserChecks
