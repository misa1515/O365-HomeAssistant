---
title: Events
nav_order: 16
---

# Events

The attribute `ha_event` shows whether the event is triggered by an HA initiated action

##  Calendar Events

Events will be raised for the following items.

- o365_create_calendar_event - Creation of a new event via the O365 integration
- o365_modify_calendar_event - Update of an event via the O365 integration
- o365_modify_calendar_recurrences - Update of a recurring event via the O365 integration
- o365_remove_calendar_event - Removal of an event via the O365 integration
- o365_remove_calendar_recurrences - Removal of a recurring event series via the O365 integration
- o365_respond_calendar_event - Response to an event via the O365 integration

The events have the following general structure:

```yaml
event_type: o365_create_calendar_event
data:
  event_id: >-
    AAMkAGQwYzQ5ZjZjLTQyYmItNDJmNy04NDNjLTJjYWY3NzMyMDBmYwBGAAAAAAC9VxHxYFrdCHSJkXtJ-BwCoiRErLbiNRJDCFyMjq4khAAY9v0_vAACoiRErLbiNRJDCFyMjq4khAAcZSY4SAAA=
  ha_event: true
origin: LOCAL
time_fired: "2023-02-19T15:29:01.962020+00:00"
context:
  id: 01GSN4NWGABVFQQWPP2D8G3CN8
  parent_id: null
  user_id: null
```

##  To-Do Events

Events will be raised for the following items.

- o365_new_todo - New to-do created either by the O365 integration or via some external app
- o365_update_todo - Update of a to-do via the O365 integration
- o365_delete_todo - Deletion of a to-do via the O365 integration
- o365_completed_todo - To-do marked complete either by the O365 integration or via some external app (`show_completed` must be enabled for to-do list in `o365_tasks_xxxx.yaml`)
- o365_uncompleted_todo - To-do marked incomplete via the O365 integration

It should be noted that actions occurring external to HA are identified via a 30-second poll, so will very likely be delayed by up to that time. Any new or completed to-do occurring within 5 minutes before HA restart will very likely have a new event sent after the restart.

The events have the following general structure. A `created` or `completed` attribute will be included where the action happened outside HA:

```yaml
event_type: o365_new_todo
data:
  todo_id: >-
    AAMkAGQwYzQ5ZjZjLTQyYmItNDJmNy04NDNjLTJjYWY3NzMyMDBGAAAAAAC9VxHxYFTdSrdCHSJkXtJ-BwCoiRErLbiNRJDCFyMjq4khAAbWN3xqAACoiRErLbiNRJDCFyMjq4khAAcZSXKvAAA=
  created: "2023-02-19T15:36:05.436266+00:00"
  ha_event: false
origin: LOCAL
time_fired: "2023-02-19T15:36:14.679300+00:00"
context:
  id: 01GSN5332Q90ZKVEX0CZQNND73
  parent_id: null
  user_id: null
```
##  Teams Status Events

Events will be raised for the following items.

- o365_update_user_status - User teams presence updated

The events have the following general structure:

```yaml
event_type: o365_update_user_status
data:
  name: Joe Teams Status
  status:
    availability: Available
    activity: Available
  ha_event: true
origin: LOCAL
time_fired: "2024-02-12T18:22:36.694771+00:00"
context:
  id: 01HPF8X14PYZ1QRZ8V199JSQTQ
  parent_id: null
  user_id: null
```

##  Teams Chat Events

Events will be raised for the following items.

- o365_send_chat_message - Message sent to specified chat via the O365 integration

The events have the following general structure:

```yaml
event_type: o365_send_chat_message
data:
  chat_id: >-
    19:5f6d6952-ace3-9999-9999-14af19704e05_99999999-a5c7-46da-8107-b25090a1ed66@unq.gbl.spaces
  ha_event: true
origin: LOCAL
time_fired: "2023-06-07T17:43:39.509758+00:00"
context:
  id: 01H2BFA0QNCGEN2ZYRWGBFFHRF
  parent_id: null
  user_id: null
```