from django import forms


class CheckoutForm(forms.Form):
    extra_phone = forms.RegexField(
        label="Дополнительный телефон", regex=r"^[+\d\s()–—-]*$", required=False, max_length=40,
        error_messages={"invalid": "Укажите телефон цифрами; допустимы +, пробелы, скобки и дефисы."},
        widget=forms.TextInput(attrs={"type": "tel", "inputmode": "tel", "autocomplete": "tel"}),
    )
    comment = forms.CharField(label="Комментарий к заказу", required=False, max_length=5000,
                              widget=forms.Textarea(attrs={"rows": 3}))


class RetailCheckoutForm(forms.Form):
    name = forms.CharField(label="Имя", max_length=160, widget=forms.TextInput(attrs={"autocomplete":"name"}))
    phone = forms.RegexField(label="Телефон", regex=r"^\+?[0-9\s()–—-]{5,40}$", max_length=40,
        widget=forms.TextInput(attrs={"type":"tel", "inputmode":"tel", "autocomplete":"tel"}),
        error_messages={"invalid":"Укажите телефон цифрами, например +7 999 123-45-67."})
    communication = forms.MultipleChoiceField(label="Предпочтительный способ связи", required=False,
        choices=[("telegram","Telegram"),("whatsapp","WhatsApp"),("phone","Звонок по телефону")], widget=forms.CheckboxSelectMultiple)
    telegram_use_phone = forms.BooleanField(label="Использовать основной телефон для Telegram", required=False)
    telegram = forms.CharField(label="Telegram: @username или номер телефона", required=False, max_length=80)
    whatsapp = forms.RegexField(label="Другой номер для WhatsApp (необязательно)", regex=r"^\+?[0-9\s()–—-]{5,40}$", required=False, max_length=40,
        widget=forms.TextInput(attrs={"type":"tel", "inputmode":"tel"}), error_messages={"invalid":"Укажите номер WhatsApp цифрами."})
    comment = forms.CharField(label="Комментарий к заказу", required=False, max_length=5000, widget=forms.Textarea(attrs={"rows":3}))

    def clean(self):
        import re
        data = super().clean()
        phone = data.get("phone", "")
        if phone and not 5 <= len(re.sub(r"\D", "", phone)) <= 15:
            self.add_error("phone", "Проверьте количество цифр в телефоне.")
        methods = data.get("communication") or ["phone"]
        data["communication"] = methods
        if "telegram" in methods:
            value = phone if data.get("telegram_use_phone") else data.get("telegram", "").strip()
            if not value or not (re.fullmatch(r"@[A-Za-z][A-Za-z0-9_]{4,31}", value) or re.fullmatch(r"\+?[0-9\s()–—-]{5,40}", value) and 5 <= len(re.sub(r"\D", "", value)) <= 15):
                self.add_error("telegram", "Укажите @username, телефон или выберите основной телефон.")
            data["telegram"] = value
        else:
            data["telegram"] = ""
        data["whatsapp"] = (data.get("whatsapp") or phone) if "whatsapp" in methods else ""
        if data["whatsapp"] and not 5 <= len(re.sub(r"\D", "", data["whatsapp"])) <= 15:
            self.add_error("whatsapp", "Проверьте номер WhatsApp.")
        return data
