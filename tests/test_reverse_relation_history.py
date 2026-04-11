from django.test import TestCase, Client
from django.contrib.auth.models import User
import json
from binder import history
from .testapp.models import ReverseParent, ReverseChild
from binder.models import install_history_signal_handlers, BinderModel


class ReverseRelationHistoryTest(TestCase):
    def setUp(self):
        u = User.objects.create_superuser("testuser", "test@example.com", "test")
        self.client = Client()
        self.client.login(username="testuser", password="test")
        # Ensure signals are installed
        install_history_signal_handlers(BinderModel)

    def test_reverse_relation_history(self):
        with history.atomic(source="test"):
            parent = ReverseParent.objects.create(name="Mom")

        with history.atomic(source="test"):
            child = ReverseChild.objects.create(name="Kid", parent=parent)

        # Check Parent history
        changesets = history.Changeset.objects.filter(
            changes__model="ReverseParent",
            changes__oid=parent.pk,
            changes__field="children",
        ).distinct()
        self.assertTrue(changesets.exists())

        change = history.Change.objects.filter(
            model="ReverseParent", oid=parent.pk, field="children"
        ).last()

        # Before should be empty or []
        before = json.loads(change.before)
        after = json.loads(change.after)

        self.assertEqual(before, [])
        self.assertIn(child.pk, after)

    def test_reverse_relation_move(self):
        with history.atomic(source="test"):
            p1 = ReverseParent.objects.create(name="P1")
            p2 = ReverseParent.objects.create(name="P2")
            c1 = ReverseChild.objects.create(name="C1", parent=p1)

        # Move C1 to P2
        with history.atomic(source="test"):
            c1.parent = p2
            c1.save()

        # P1 should show removal
        change_p1 = history.Change.objects.filter(
            model="ReverseParent", oid=p1.pk, field="children"
        ).last()
        self.assertIn(c1.pk, json.loads(change_p1.before))
        self.assertNotIn(c1.pk, json.loads(change_p1.after))

        # P2 should show addition
        change_p2 = history.Change.objects.filter(
            model="ReverseParent", oid=p2.pk, field="children"
        ).last()
        self.assertNotIn(c1.pk, json.loads(change_p2.before))
        self.assertIn(c1.pk, json.loads(change_p2.after))

    def test_reverse_relation_delete(self):
        with history.atomic(source="test"):
            p1 = ReverseParent.objects.create(name="P1")
            c1 = ReverseChild.objects.create(name="C1", parent=p1)

        c1_pk = c1.pk

        # Delete child
        with history.atomic(source="test"):
            c1.delete()

        # P1 should show removal
        change_p1 = history.Change.objects.filter(
            model="ReverseParent", oid=p1.pk, field="children"
        ).last()
        self.assertIn(c1_pk, json.loads(change_p1.before))
        self.assertNotIn(c1_pk, json.loads(change_p1.after))
