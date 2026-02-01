from django.test import TestCase, Client
from django.contrib.auth.models import User
import json
from binder import history
from .testapp.models import ReverseParentNoChildHistory, ReverseChildNoHistory
from binder.models import install_history_signal_handlers, BinderModel


class ReverseRelationNoChildHistoryTest(TestCase):
    def setUp(self):
        u = User.objects.create_superuser("testuser", "test@example.com", "test")
        self.client = Client()
        self.client.login(username="testuser", password="test")
        # Ensure signals are installed
        install_history_signal_handlers(BinderModel)

    def test_reverse_relation_no_child_history(self):
        with history.atomic(source="test"):
            parent = ReverseParentNoChildHistory.objects.create(name="Mom")

        with history.atomic(source="test"):
            child = ReverseChildNoHistory.objects.create(name="Kid", parent=parent)

        # Check Parent history
        changesets = history.Changeset.objects.filter(
            changes__model="ReverseParentNoChildHistory",
            changes__oid=parent.pk,
            changes__field="children",
        ).distinct()
        self.assertTrue(changesets.exists())

        change = history.Change.objects.filter(
            model="ReverseParentNoChildHistory", oid=parent.pk, field="children"
        ).last()

        # Before should be empty or []
        before = json.loads(change.before)
        after = json.loads(change.after)

        self.assertEqual(before, [])
        self.assertIn(child.pk, after)
