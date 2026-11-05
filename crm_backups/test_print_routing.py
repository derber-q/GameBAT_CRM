import uuid
from django.test import TestCase,override_settings
from django.core.exceptions import ValidationError
from sales.models import PrintAgent
from sales.print_agents import configured_agent
from .models import PrintRouting


class PrintRoutingTests(TestCase):
    def agent(self,name):
        return PrintAgent.objects.create(name=name,printer_name=name,token_hash=uuid.uuid4().hex*2)

    @override_settings(PRINT_AGENT_ID='')
    def test_one_printer_compatibility_and_multiple_explicit_target(self):
        first=self.agent('first')
        self.assertEqual(configured_agent().pk,first.pk)
        second=self.agent('second')
        with self.assertRaises(ValidationError):configured_agent()
        PrintRouting.objects.create(pk=1,default_agent=second)
        self.assertEqual(configured_agent().pk,second.pk)
        second.enabled=False;second.save()
        with self.assertRaises(ValidationError):configured_agent()
