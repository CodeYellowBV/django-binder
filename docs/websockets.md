# Websockets

Binder.websockets contains functions to connect with a [high-templar](https://github.com/CodeYellowBV/high-templar) instance.

## Flow

The client = a web/native/whatever frontend
The websocket server = a high-templar instance
The binder app = a server created with django-binder

- The client needs live updates of certain models.
- The client opens a websocket connection
- The websocket server asks the binder instance if this user is allowed to open a websocket connection, by creating a request to `/api/bootstrap/`
- The websocket server parses the bootstrap response, and lists the allowed_rooms for the user on the websocket.
- The client can subscribe to a room
- When the binder instance POSTs a `/trigger/` to the websocket server, the high-templar instances publishes the data from the trigger to the specified rooms.
- Every client subscribed to one of those rooms will receive that publish event.

## Rooms

The scoping of subscriptions is done through rooms. Roomnames are dictionaries. When a user opens a websocket, the high-templar receives a list of allowed_rooms from the binder instance. The user can only subscribe to a room if there exists a room in the allowed_rooms list, where every key-value matches with the room from the subscription request.

## Room scoping example

There is a chat application for a company. A manager can only view messages of a single location.

The allowed_rooms of a manager of the eindhoven branch could look like
```
[{'location': 'Eindhoven'}]
```

If there would be a CEO who can view messages of every location, his allowed rooms would look like:
```
[{'location': 'Eindhoven'}, {'location': 'Utrecht'}, {'location': 'Delft'}]
```

If you don't feel like listing every single location the company has in the allowed_rooms, you could use the wildcard syntax:
```
[{'location': '*'}]
```

Note: this doesn't mean a client can subscribe to room: `{'location': '*'}` and will receive every message from all the location rooms. A client needs to subscribe to a specific room, the wildcard is just a shorthand in the allowed rooms.

If you do really need a room with messages from all locations, just trigger twice: once in the location specific room and one in the location: * room.

## Trigger on saves
Since sending websocket updates upon saving models is something we often need, there is a 'shortcut' for this.
If you set `push_websocket_updates_upon_save` to `True` in a model, it will automatically send websocket updates whenever it is saved or deleted.

```python
class Country(BinderModel):
    push_websocket_updates_upon_save = True
    name = models.CharField(unique=True, max_length=100)
```
For instance, whenever a `Country` is saved, it will trigger a websocket update to `auto-updates/country` with `data = country.id`.

### Custom object managers
Normally, websocket updates are also sent when an object is bulk created/updated/deleted. This is implemented by using a custom objects `Manager`.
This is usually just an implementation detail, but it can be problematic when your model *also* has its own custom objects `Manager`.
If you want to make bulk updating push websocket notifications, you need to ensure that your custom manager inherits from `binder.models.BinderManager`.

### Forcing websocket updates
If you want stores to re-fetch your objects, but you haven't saved them directly (e.g. when you changed related objects or annotation values),
you can forcibly send a websocket update by calling the `push_default_websocket_update()` class method on the model.


## Binder setup

The high-templar instance is agnostic of the authentication/datamodel/permissions. The authentication is done by the proxy to /api/bootstrap. The datamodel / permission stuff is all done through rooms and the data that gets sent through it.

`binder.websocket` provides 2 helpers for communicating with high-templar.

### RoomController

**Binder needs to return the allowed_rooms for a user in the bootstrap response**
The binder.websocket.RoomController is a helper for this. You can register it just like the router in urls.py as follows:

```
router = binder.router.Router().register(binder.views.ModelView)
room_controller = binder.websocket.RoomController().register(binder.views.ModelView)
```

And then in views/bootstrap:
```
from ..urls import room_controller
...

return JsonResponse({
	'allowed_rooms': room_controller.list_rooms_for_user(request.user),
	...
```

The RoomController checks every descendant of the ModelView and looks for a  `@classmethod get_rooms_for_user(cls, user)`. The list_rooms_for_user is a merged list of the results for that user.

### Trigger

`binder.websocket` provides a `trigger` to the high_templar instance using a POST request. The url for this request is `getattr(settings, 'HIGH_TEMPLAR_URL', 'http://localhost:8002')`. It needs `data, rooms` as args, the data which will be sent in the publish and the rooms it will be publishes to.
