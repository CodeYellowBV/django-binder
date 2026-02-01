# flake8: noqa
import os

# We have it all, from A to Z!
from .animal import Animal
from .donor import Donor
from .caretaker import Caretaker
from .contact_person import ContactPerson
from .costume import Costume
from .gate import Gate
from .nickname import Nickname, NullableNickname
from .lion import Lion
from .picture import Picture
from .zoo import Zoo
from .zoo_employee import ZooEmployee
from .city import City, CityState, PermanentCity
from .country import Country
from .web_page import WebPage
from .pet import Pet
from .reverse_config_models import (
    ReverseParent,
    ReverseChild,
    ReverseParentNoChildHistory,
    ReverseChildNoHistory,
)

# This is Postgres-specific
if os.environ.get("BINDER_TEST_MYSQL", "0") != "1":
    from .timetable import TimeTable
    from .feeding_schedule import FeedingSchedule
